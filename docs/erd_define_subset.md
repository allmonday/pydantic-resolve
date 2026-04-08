# ERD with DefineSubset

[中文版](./erd_define_subset.zh.md)

When response models should expose only a subset of entity fields — for example, hiding `owner_id` from external APIs — `DefineSubset` lets you pick specific fields while keeping relationship declarations centralized.

## The Problem

ERD entities often contain internal fields that should not appear in API responses:

```python
class TaskEntity(BaseModel, BaseEntity):
    id: int
    title: str
    owner_id: int        # internal FK, should not leak to API
    sprint_id: int       # internal FK, should not leak to API
    internal_notes: str  # internal field
```

You could create a separate response model from scratch, but that duplicates field definitions and loses the ERD relationship wiring.

## Basic Usage

`DefineSubset` creates a new model with only the fields you specify:

```python
from typing import Annotated, Optional

from pydantic_resolve import DefineSubset

class TaskSummary(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'title'))
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
```

This creates a class equivalent to:

```python
class TaskSummary(BaseModel):
    id: int      # inherited from TaskEntity
    title: str   # inherited from TaskEntity
    owner: Optional[UserEntity] = None  # added by you with AutoLoad
```

The `owner_id` FK field is not part of the response, but `AutoLoad` still knows how to resolve the relationship because the ERD metadata is preserved.

## SubsetConfig for More Control

For advanced cases, use `SubsetConfig` instead of a tuple:

```python
from pydantic_resolve import SubsetConfig

class TaskDetail(DefineSubset):
    __subset__ = SubsetConfig(
        kls=TaskEntity,
        fields=['id', 'title', 'sprint_id'],
    )
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
    sprint: Annotated[Optional[SprintEntity], AutoLoad()] = None
```

### SubsetConfig Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `kls` | `type[BaseModel]` | The source entity class |
| `fields` | `list[str] \| "all" \| None` | Fields to include (mutually exclusive with `omit_fields`) |
| `omit_fields` | `list[str] \| None` | Fields to exclude (mutually exclusive with `fields`) |
| `expose_as` | `list[tuple[str, str]] \| None` | Field and alias pairs for `ExposeAs` |
| `send_to` | `list[tuple[str, tuple[str, ...] \| str]] \| None` | Field and collector target pairs for `SendTo` |
| `excluded_fields` | `list[str] \| None` | Fields to mark as `Field(exclude=True)` |

### Omitting Fields

Include all fields except specific ones:

```python
class TaskPublic(DefineSubset):
    __subset__ = SubsetConfig(
        kls=TaskEntity,
        omit_fields=['internal_notes', 'audit_log'],
    )
```

### With expose_as and send_to

```python
class TaskWithAnnotations(DefineSubset):
    __subset__ = SubsetConfig(
        kls=TaskEntity,
        fields=['id', 'title', 'name'],
        expose_as=[('name', 'task_name')],
        send_to=[('id', 'task_ids')],
    )
```

This is equivalent to adding annotations to the fields:

```python
class TaskWithAnnotations(BaseModel):
    id: Annotated[int, SendTo('task_ids')]
    title: str
    name: Annotated[str, ExposeAs('task_name')]
```

## DefineSubset vs Regular Inheritance

Both approaches create a new model, but they serve different purposes:

| Feature | `DefineSubset` | Regular inheritance |
|---------|---------------|-------------------|
| Field selection | Explicit list or omit | All fields inherited |
| FK field hiding | Automatic | Must override |
| ERD relationship access | Preserved via metadata | Must be explicit |
| Validation against source | Built-in | None |

### Regular Inheritance (for comparison)

```python
class TaskView(TaskEntity):
    # All fields from TaskEntity are inherited, including owner_id
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
```

### DefineSubset (hides FK fields)

```python
class TaskSummary(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'title'))
    # owner_id is NOT part of the response
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
```

## Complete Example

```python
from typing import Annotated, Optional

from pydantic import BaseModel
from pydantic_resolve import (
    DefineSubset,
    Relationship,
    base_entity,
    build_list,
    build_object,
    config_global_resolver,
)


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
    sprint_id: int


class SprintEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='id', name='tasks', target=list[TaskEntity], loader=task_loader)
    ]
    id: int
    name: str


diagram = BaseEntity.get_diagram()
AutoLoad = diagram.create_auto_load()
config_global_resolver(diagram)


# --- Subsets hide internal FK fields ---
class UserSummary(DefineSubset):
    __subset__ = (UserEntity, ('id', 'name'))


class TaskSummary(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'title'))
    owner: Annotated[Optional[UserSummary], AutoLoad()] = None


class SprintSummary(DefineSubset):
    __subset__ = (SprintEntity, ('id', 'name'))
    tasks: Annotated[list[TaskSummary], AutoLoad()] = []
    task_count: int = 0

    def post_task_count(self):
        return len(self.tasks)


# --- Resolve ---
raw_sprints = [{"id": 1, "name": "Sprint 24"}]
sprints = [SprintSummary.model_validate(s) for s in raw_sprints]
sprints = await Resolver().resolve(sprints)

print(sprints[0].model_dump())
# {'id': 1, 'name': 'Sprint 24',
#  'tasks': [
#      {'id': 10, 'title': 'Design docs', 'owner': {'id': 7, 'name': 'Ada'}},
#      {'id': 11, 'title': 'Refine examples', 'owner': {'id': 8, 'name': 'Bob'}},
#  ],
#  'task_count': 2}
# Note: no owner_id or sprint_id in the output
```

## Next

Continue to [ORM Integration](./orm_integration.md) to learn how to auto-generate loaders from SQLAlchemy, Django, or Tortoise ORM.
