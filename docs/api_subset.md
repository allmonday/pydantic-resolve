# DefineSubset API

[中文版](./api_subset.zh.md)

## DefineSubset

```python
from pydantic_resolve import DefineSubset

class MySubset(DefineSubset):
    __subset__ = (SourceEntity, ('field1', 'field2'))
    # or
    __subset__ = SubsetConfig(kls=SourceEntity, fields=['field1', 'field2'])
```

Creates a new Pydantic model with selected fields from the source entity. You can add additional fields (including `AutoLoad` annotations) on top.

### Tuple Form

```python
class TaskSummary(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'title'))
```

Equivalent to `SubsetConfig(kls=TaskEntity, fields=['id', 'title'])`.

## SubsetConfig

```python
from pydantic_resolve import SubsetConfig

SubsetConfig(
    kls: type[BaseModel],
    fields: list[str] | Literal["all"] | None = None,
    omit_fields: list[str] | None = None,
    expose_as: list[tuple[str, str]] | None = None,
    send_to: list[tuple[str, tuple[str, ...] | str]] | None = None,
    excluded_fields: list[str] | None = None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `kls` | `type[BaseModel]` | Source entity class |
| `fields` | `list[str] \| "all" \| None` | Fields to include (mutually exclusive with `omit_fields`) |
| `omit_fields` | `list[str] \| None` | Fields to exclude (mutually exclusive with `fields`) |
| `expose_as` | `list[tuple[str, str]] \| None` | `(field_name, alias)` pairs for ExposeAs |
| `send_to` | `list[tuple[str, str \| tuple]] \| None` | `(field_name, collector_name)` pairs for SendTo |
| `excluded_fields` | `list[str] \| None` | Fields marked as `Field(exclude=True)` |

### Example with All Options

```python
class TaskSummary(DefineSubset):
    __subset__ = SubsetConfig(
        kls=TaskEntity,
        fields=['id', 'title', 'name'],
        expose_as=[('name', 'task_name')],
        send_to=[('id', 'task_ids')],
        excluded_fields=['internal_flag'],
    )
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
```
