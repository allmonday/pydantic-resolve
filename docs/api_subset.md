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

If an added field maps to an ERD relationship, `DefineSubset` automatically injects the required FK field as a hidden `exclude=True` field when needed. This works for both:

- implicit relationship matching by field name
- explicit `AutoLoad(origin=...)` aliases

Example:

```python
class TaskCard(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'title'))

    # field name differs from relationship name `owner`
    my_owner: Annotated[Optional[UserEntity], AutoLoad(origin='owner')] = None
```

Even though `owner_id` is not part of the subset fields, `DefineSubset` adds it internally so the generated resolve method can still load `my_owner`.

### External ErDiagram Constraint

When `DefineSubset` relies on external `ErDiagram(...)` definitions instead of `base_entity()`, it may need to infer the FK field before a resolver instance is created.

If multiple external diagrams register the same model class with the same relationship `name` but different `fk` values, subset construction is ambiguous and now raises `ValueError`.

Keep one authoritative external relationship definition per `(model class, relationship name)`, or explicitly include the FK field in the subset so no hidden-field inference is needed.

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
