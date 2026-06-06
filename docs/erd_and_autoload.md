# ERD and AutoLoad

[中文版](./erd_and_autoload.zh.md)

Manual `resolve_*` methods are the right entry point. But once the same relationships start repeating across multiple response models, the question changes: you are no longer asking "how do I load this field?" but "where should the source of truth for this relationship live?"

ERD mode centralizes relationship declarations into entity classes. `AutoLoad` removes the need to write `resolve_*` at all.

## The Duplication Signal

If your codebase starts to accumulate patterns like these, relationships are ready to move into ERD:

- `TaskCard.resolve_owner`
- `TaskDetail.resolve_owner`
- `SprintBoard.resolve_tasks`
- `SprintReport.resolve_tasks`

The loader logic is still correct, but the relationship knowledge is now duplicated.

## Cost vs Benefit

| Question | Manual Core API | ERD + `AutoLoad` |
|---|---|---|
| First endpoint | Faster | Slower |
| Upfront setup | Low | Medium |
| Reusing the same relation in many models | Repetitive | Centralized |
| Changing a relation later | Update many `resolve_*` methods | Update one declaration |
| GraphQL and MCP reuse | Separate work | Natural extension |

## Goal

Same `Sprint -> Task -> User` scenario. The output is identical to the Core API version — the difference is that `resolve_owner` and `resolve_tasks` disappear from the view models.

## Step 1: Define Entities with Relationships

Relationship declarations move from view models into entity classes:

```python
from pydantic_resolve import Relationship, base_entity, config_global_resolver


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
```

## Step 2: Create AutoLoad and Configure the Resolver

```python
diagram = BaseEntity.get_diagram()
AutoLoad = diagram.create_auto_load()
config_global_resolver(diagram)
```

These three lines wire the ERD into the resolver. `AutoLoad` embeds diagram-specific metadata into the annotation.

## Step 3: Replace resolve_* with AutoLoad Annotations

View models inherit from entities. Relationship fields use `AutoLoad()` instead of `resolve_*`:

```python
class TaskView(TaskEntity):
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None  # (1)


class SprintView(SprintEntity):
    tasks: Annotated[list[TaskView], AutoLoad()] = []
    task_count: int = 0

    def post_task_count(self):  # (2)
        return len(self.tasks)
```

1.  `AutoLoad()` looks up the `Relationship` with `name='owner'` from the diagram and generates an equivalent `resolve_owner` at analysis time.
2.  `post_*` stays exactly the same — ERD removes relationship wiring, not business-specific post-processing.

## Step 4: Run the Resolver

```python
raw_sprints = [
    {"id": 1, "name": "Sprint 24"},
    {"id": 2, "name": "Sprint 25"},
]
sprints = [SprintView.model_validate(s) for s in raw_sprints]
sprints = await Resolver().resolve(sprints)

for s in sprints:
    print(s.model_dump())
```

Output:

```python
{'id': 1, 'name': 'Sprint 24',
 'tasks': [
     {'id': 10, 'title': 'Design docs', 'owner_id': 7, 'owner': {'id': 7, 'name': 'Ada'}},
     {'id': 11, 'title': 'Refine examples', 'owner_id': 8, 'owner': {'id': 8, 'name': 'Bob'}},
 ],
 'task_count': 2}
{'id': 2, 'name': 'Sprint 25',
 'tasks': [
     {'id': 12, 'title': 'Bug fixes', 'owner_id': 7, 'owner': {'id': 7, 'name': 'Ada'}},
 ],
 'task_count': 1}
```

## What Changed

Compared with the Core API version:

- `resolve_owner` disappeared.
- `resolve_tasks` disappeared.
- Relationship declarations live in one place (`__relationships__`).
- `post_task_count` is unchanged.

## How AutoLoad Works

`AutoLoad` is not magic. When the resolver scans a class:

1. It finds the `AutoLoad()` annotation on a field.
2. It looks up the `Relationship` by name from the diagram.
3. It generates an equivalent `resolve_*` method that calls the loader with the FK value.

If the field name does not match the relationship name, use the `origin` parameter:

```python
class SprintView(SprintEntity):
    items: Annotated[list[TaskView], AutoLoad(origin='tasks')] = []
```

## Two Ways to Declare the ERD

### Inline `__relationships__` on Entity Classes

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

Best when relationship metadata belongs naturally on the entity type.

### External `ErDiagram(...)` Declaration

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

Best when you don't want to modify entity classes, or when the same classes are shared across modules.

!!! warning "One diagram per project"

    With external `ErDiagram(...)`, all entities register into a shared internal registry. Multiple `ErDiagram` instances with overlapping entities produce unpredictable results.

    If you need to merge relationships from different sources, use `add_relationship()`:

    ```python
    diagram = ErDiagram(entities=[...])
    diagram = diagram.add_relationship(more_entities)
    ```

## Relationship Types

### One-to-One

```python
Relationship(
    fk='owner_id',
    name='owner',
    target=UserEntity,
    loader=user_loader
)
```

### One-to-Many

```python
Relationship(
    fk='id',
    name='tasks',
    target=list[TaskEntity],
    loader=task_loader
)
```

### Handling None FK Values

```python
Relationship(
    fk='owner_id',
    name='owner',
    target=UserEntity,
    loader=user_loader,
    fk_none_default=None
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

```python
Relationship(
    fk='tag_ids',             # comma-separated string "1,2,3"
    name='tags',
    target=list[TagEntity],
    loader=tag_loader,
    load_many=True,
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
    comments: list[CommentView] = []

    def resolve_comments(self, loader=Loader(comment_loader)):  # manual
        return loader.load(self.id)
```

## Custom Resolver

If you prefer not to use the global resolver:

```python
from pydantic_resolve import config_resolver

MyResolver = config_resolver('MyResolver', er_diagram=diagram)
result = await MyResolver().resolve(data)
```

## Handling Circular Imports

### Same-Module String References

```python
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='owner_id', name='owner', target='UserEntity', loader=user_loader)
    ]
```

### Cross-Module References

```python
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(
            fk='owner_id',
            target='app.models.user:UserEntity',
            name='owner',
            loader=user_loader
        )
    ]
```

Supported formats:

- Simple class names: `'UserEntity'`
- Module path syntax: `'app.models.user:UserEntity'`
- List generics: `list['UserEntity']` or `list['app.models.user:UserEntity']`

## When Not to Use ERD Yet

Stay with manual Core API when:

- you only have a few response models
- the relationship structure is still moving quickly
- the duplication cost is not real yet

ERD is a scaling step, not a rite of passage.

## Next

- [ERD with DefineSubset](./erd_define_subset.md) — hide internal FK fields from responses.
- [DataLoader Deep Dive](./dataloader_deep_dive.md) — understand how batching works under the hood.
