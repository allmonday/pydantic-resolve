# ERD and AutoLoad

[中文版](./erd_and_autoload.zh.md)

Manual `resolve_*` methods are the right entry point. But once the same relationships start repeating across multiple response models, the problem changes.

You are no longer asking "how do I load this field?" You are asking "where should the source of truth for this relationship live?"

That is the point where ERD mode becomes worth the upfront cost.

## The Duplication Signal

If your codebase starts to accumulate patterns like these, the relationships are probably ready to move into ERD:

- `TaskCard.resolve_owner`
- `TaskDetail.resolve_owner`
- `SprintBoard.resolve_tasks`
- `SprintReport.resolve_tasks`

The loader logic may still be correct, but the relationship knowledge is now duplicated.

## Cost vs Benefit

| Question | Manual Core API | ERD + `AutoLoad` |
|---|---|---|
| First endpoint | Faster | Slower |
| Upfront setup | Low | Medium |
| Reusing the same relation in many models | Repetitive | Centralized |
| Changing a relation later | Update many `resolve_*` methods | Update one declaration |
| GraphQL and MCP reuse | Separate work | Natural extension |

## The Same Scenario in ERD Mode

```python
from typing import Annotated, Optional

from pydantic import BaseModel
from pydantic_resolve import (
    Loader,
    Resolver,
    Relationship,
    base_entity,
    build_list,
    build_object,
    config_global_resolver,
)


# --- Fake database ---
USERS = {
    7: {"id": 7, "name": "Ada"},
    8: {"id": 8, "name": "Bob"},
}

TASKS = [
    {"id": 10, "title": "Design docs", "sprint_id": 1, "owner_id": 7},
    {"id": 11, "title": "Refine examples", "sprint_id": 1, "owner_id": 8},
]


async def user_loader(user_ids: list[int]):
    users = [USERS.get(uid) for uid in user_ids]
    return build_object(users, user_ids, lambda u: u.id)


async def task_loader(sprint_ids: list[int]):
    tasks = [t for t in TASKS if t["sprint_id"] in sprint_ids]
    return build_list(tasks, sprint_ids, lambda t: t["sprint_id"])


# --- Entity definitions ---
BaseEntity = base_entity()


class UserEntity(BaseModel, BaseEntity):
    id: int
    name: str


class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='owner_id', name='owner', target=UserEntity, loader=user_loader)
    ]
    id: int
    title: str
    owner_id: int


class SprintEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='id', name='tasks', target=list[TaskEntity], loader=task_loader)
    ]
    id: int
    name: str


diagram = BaseEntity.get_diagram()
AutoLoad = diagram.create_auto_load()
config_global_resolver(diagram)


# --- Response models (no resolve_* methods needed) ---
class TaskView(TaskEntity):
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None


class SprintView(SprintEntity):
    tasks: Annotated[list[TaskView], AutoLoad()] = []
    task_count: int = 0

    def post_task_count(self):
        return len(self.tasks)


# --- Resolve ---
raw_sprints = [{"id": 1, "name": "Sprint 24"}]
sprints = [SprintView.model_validate(s) for s in raw_sprints]
sprints = await Resolver().resolve(sprints)

print(sprints[0].model_dump())
# {'id': 1, 'name': 'Sprint 24',
#  'tasks': [
#      {'id': 10, 'title': 'Design docs', 'owner_id': 7,
#       'owner': {'id': 7, 'name': 'Ada'}},
#      {'id': 11, 'title': 'Refine examples', 'owner_id': 8,
#       'owner': {'id': 8, 'name': 'Bob'}},
#  ],
#  'task_count': 2}
```

## What Changed

- `resolve_owner` disappeared from the view model.
- `resolve_tasks` disappeared from the view model.
- Relationship declarations moved into `__relationships__`.
- `post_task_count` stayed exactly where it belongs.

That last point matters: ERD removes repeated relationship wiring, but it does not replace business-specific post-processing.

## Two Ways to Declare the ERD

### Style 1: Inline `__relationships__` on Entity Classes

```python
BaseEntity = base_entity()

class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='owner_id', name='owner', target=UserEntity, loader=user_loader)
    ]
    id: int
    title: str
    owner_id: int

diagram = BaseEntity.get_diagram()
```

This style works well when the entity class is already owned by the current application layer and you are comfortable attaching relationship metadata directly to it.

### Style 2: External `ErDiagram(...)` Declaration

```python
from pydantic_resolve import Entity, ErDiagram

class UserEntity(BaseModel):
    id: int
    name: str

class TaskEntity(BaseModel):
    id: int
    title: str
    owner_id: int

class SprintEntity(BaseModel):
    id: int
    name: str

diagram = ErDiagram(
    entities=[
        Entity(kls=TaskEntity, relationships=[
            Relationship(fk='owner_id', name='owner', target=UserEntity, loader=user_loader)
        ]),
        Entity(kls=SprintEntity, relationships=[
            Relationship(fk='id', name='tasks', target=list[TaskEntity], loader=task_loader)
        ]),
        Entity(kls=UserEntity, relationships=[]),
    ],
)
```

### When External Declaration Is a Better Fit

External `ErDiagram(...)` declaration is often the better choice when:

- you do not want to modify the entity classes themselves
- the same entity classes are shared across multiple modules or services
- you want one centralized place to inspect all relationship definitions
- the source classes come from another package or a compatibility layer

In short:

- use `__relationships__` when relationship metadata belongs naturally on the entity type
- use external `ErDiagram(...)` when relationship metadata should stay separate from the type definition

## How AutoLoad Works

`AutoLoad` is not magic. It is an annotation that the resolver recognizes and converts into a `resolve_*` method at analysis time.

```python
AutoLoad = diagram.create_auto_load()

class TaskView(TaskEntity):
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
```

When the resolver scans this class, it:

1. Finds the `AutoLoad()` annotation on the `owner` field.
2. Looks up the `Relationship` with `name='owner'` from the diagram.
3. Generates an equivalent `resolve_owner` method that calls the loader with the FK value.

The `AutoLoad(origin='tasks')` parameter lets you specify a different relationship name when the field name does not match:

```python
class SprintView(SprintEntity):
    items: Annotated[list[TaskView], AutoLoad(origin='tasks')] = []
```

## The diagram and AutoLoad Must Match

This setup is not just ceremony:

```python
diagram = BaseEntity.get_diagram()
AutoLoad = diagram.create_auto_load()
config_global_resolver(diagram)
```

`create_auto_load()` embeds diagram-specific relationship metadata into the annotation, so the resolver must be configured with the same `diagram`.

If you use a custom resolver instead of the global one:

```python
from pydantic_resolve import config_resolver

MyResolver = config_resolver('MyResolver', er_diagram=diagram)
result = await MyResolver().resolve(data)
```

## Relationship Types

### One-to-One (build_object)

```python
Relationship(
    fk='owner_id',           # the FK field on this entity
    name='owner',            # unique relationship name
    target=UserEntity,       # single target entity
    loader=user_loader       # returns one item per key
)
```

### One-to-Many (build_list)

```python
Relationship(
    fk='id',                 # the PK field on this entity
    name='tasks',            # unique relationship name
    target=list[TaskEntity], # list target
    loader=task_loader       # returns a list of items per key
)
```

### Handling None FK Values

```python
Relationship(
    fk='owner_id',
    name='owner',
    target=UserEntity,
    loader=user_loader,
    fk_none_default=None              # return None when FK is None
)

# Or use a factory:
Relationship(
    fk='owner_id',
    name='owner',
    target=UserEntity,
    loader=user_loader,
    fk_none_default_factory=lambda: AnonymousUser()
)
```

### Multiple Relationships from the Same FK

```python
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='owner_id', name='author', target=UserEntity, loader=user_loader),
        Relationship(fk='owner_id', name='reviewer', target=UserEntity, loader=reviewer_loader),
    ]
    id: int
    owner_id: int
```

### Custom FK Transformation with fk_fn

When the FK value needs transformation before being passed to the loader:

```python
Relationship(
    fk='tag_ids',             # comma-separated string "1,2,3"
    name='tags',
    target=list[TagEntity],
    loader=tag_loader,
    load_many=True,           # use load_many instead of load
    load_many_fn=lambda ids: ids.split(',') if ids else []
)
```

## Migrating from Manual resolve_* to ERD

The migration path is incremental:

1. Define entities that mirror your existing response models.
2. Add `__relationships__` or external `ErDiagram` declarations.
3. Create `AutoLoad` and `config_global_resolver`.
4. Replace `resolve_*` methods with `AutoLoad()` annotations.
5. Keep `post_*` methods unchanged.

You can mix manual and ERD-driven resolution in the same project:

```python
class TaskView(TaskEntity):
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None  # ERD-driven
    comments: list[CommentView] = []                            # still manual

    def resolve_comments(self, loader=Loader(comment_loader)):  # manual
        return loader.load(self.id)
```

## Handling Circular Imports

When entities reference each other through `target`, you may encounter circular import issues.

### Same-Module String References

```python
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        # String 'UserEntity' resolved within same module
        Relationship(fk='owner_id', name='owner', target='UserEntity', loader=user_loader)
    ]
```

### Cross-Module References

```python
# In app/models/task.py
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(
            fk='owner_id',
            target='app.models.user:UserEntity',  # module.path:ClassName
            name='owner',
            loader=user_loader
        )
    ]
```

The `_resolve_ref` function supports:

- Simple class names: `'UserEntity'` (looked up in the current module)
- Module path syntax: `'app.models.user:UserEntity'`
- List generics: `list['UserEntity']` or `list['app.models.user:UserEntity']`

## When Not to Use ERD Yet

Stay with manual Core API when:

- you only have a few response models
- the relationship structure is still moving quickly
- the duplication cost is not real yet

ERD is valuable, but it is a scaling step, not a rite of passage.

## Next

Continue to [DataLoader Deep Dive](./dataloader_deep_dive.md) to understand how batching works under the hood, or jump to [ERD with DefineSubset](./erd_define_subset.md) to learn how to hide internal FK fields from responses.
