# ERD with DefineSubset

[中文版](./erd_define_subset.zh.md)

Entity fields like `owner_id` and `sprint_id` are internal details. `DefineSubset` lets you pick specific fields for the API response while keeping ERD relationship wiring intact.

## Goal

You have an entity with internal FK fields:

```python
class TaskEntity(BaseModel, BaseEntity):
    id: int
    title: str
    owner_id: int        # internal FK
    sprint_id: int       # internal FK
```

You want the API response to include the `owner` relationship but **not** the `owner_id` FK field:

```json
[
    {
        "id": 1,
        "name": "Sprint 24",
        "tasks": [
            {"id": 10, "title": "Design docs", "owner": {"id": 7, "name": "Ada"}},
            {"id": 11, "title": "Refine examples", "owner": {"id": 8, "name": "Bob"}}
        ],
        "task_count": 2
    }
]
```

No `owner_id`, no `sprint_id` in the output.

## Step 1: Define Subsets for Each Entity

`DefineSubset` creates a new model with only the fields you specify:

```python
from pydantic_resolve import DefineSubset


class UserSummary(DefineSubset):
    __subset__ = (UserEntity, ('id', 'name'))


class TaskSummary(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'title'))  # (1)
    owner: Annotated[Optional[UserSummary], AutoLoad()] = None  # (2)
```

1.  Only `id` and `title` are included — `owner_id` and `sprint_id` are excluded from the response.
2.  `AutoLoad` still resolves the relationship because ERD metadata is preserved, even though the FK field is not in the subset.

This is equivalent to:

```python
class TaskSummary(BaseModel):
    id: int
    title: str
    owner: Optional[UserSummary] = None
```

## Step 2: Compose the Sprint Response

```python
class SprintSummary(DefineSubset):
    __subset__ = (SprintEntity, ('id', 'name'))
    tasks: Annotated[list[TaskSummary], AutoLoad()] = []
    task_count: int = 0

    def post_task_count(self):
        return len(self.tasks)
```

## Step 3: Run the Resolver

```python
raw_sprints = [
    {"id": 1, "name": "Sprint 24"},
    {"id": 2, "name": "Sprint 25"},
]
sprints = [SprintSummary.model_validate(s) for s in raw_sprints]
sprints = await Resolver().resolve(sprints)

for s in sprints:
    print(s.model_dump())
```

Output:

```python
{'id': 1, 'name': 'Sprint 24',
 'tasks': [
     {'id': 10, 'title': 'Design docs', 'owner': {'id': 7, 'name': 'Ada'}},
     {'id': 11, 'title': 'Refine examples', 'owner': {'id': 8, 'name': 'Bob'}},
 ],
 'task_count': 2}
{'id': 2, 'name': 'Sprint 25',
 'tasks': [
     {'id': 12, 'title': 'Bug fixes', 'owner': {'id': 7, 'name': 'Ada'}},
 ],
 'task_count': 1}
```

No `owner_id` or `sprint_id` in the output.

## DefineSubset vs Regular Inheritance

| Feature | `DefineSubset` | Regular inheritance |
|---------|---------------|-------------------|
| Field selection | Explicit list or omit | All fields inherited |
| FK field hiding | Automatic | Must override |
| ERD relationship access | Preserved via metadata | Must be explicit |

```python
# Regular inheritance: owner_id leaks into the response
class TaskView(TaskEntity):
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None

# DefineSubset: owner_id is excluded
class TaskSummary(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'title'))
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
```

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

Equivalent to:

```python
class TaskWithAnnotations(BaseModel):
    id: Annotated[int, SendTo('task_ids')]
    title: str
    name: Annotated[str, ExposeAs('task_name')]
```

## Next

Continue to [ORM Integration](./orm_integration.md) to learn how to auto-generate loaders from SQLAlchemy, Django, or Tortoise ORM.
