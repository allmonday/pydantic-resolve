# Migration Guide (v3 to v4)

v4.0 introduces breaking changes to the ER Diagram API, simplifying how relationships are defined.

## 1. Relationship parameter renames

| v3 | v4 | Description |
|----|----|-------------|
| `field` | `fk` | FK field name on this entity |
| `target_kls` | `target` | Target entity class |
| `field_fn` | `fk_fn` | Transform function applied to FK value |
| `field_none_default` | `fk_none_default` | Default when FK is None |
| `field_none_default_factory` | `fk_none_default_factory` | Factory for None default |

```python
# v3
Relationship(field='user_id', target_kls=User, loader=user_loader)
Relationship(field='id', target_kls=list[Post], field_none_default_factory=list, loader=post_loader)

# v4
Relationship(fk='user_id', target=User, loader=user_loader, name='owner')
Relationship(fk='id', target=list[Post], fk_none_default_factory=list, loader=post_loader, name='posts')
```

## 2. Relationship `name` is now required (replaces `default_field_name`)

`name` is the unique identifier for each relationship. It serves as the GraphQL field name and the lookup key for `AutoLoad`.

```python
# v3: default_field_name was optional
Relationship(field='owner_id', target_kls=User, loader=user_loader, default_field_name='owner')

# v4: name is required
Relationship(fk='owner_id', target=User, loader=user_loader, name='owner')
```

## 3. `LoadBy` replaced by `AutoLoad`

`AutoLoad` no longer requires a FK field name. It resolves the relationship by matching the field name against relationship `name` values. If the field name differs from the relationship name, use the `origin` parameter.

`AutoLoad` is not a global helper. It must be created from the same `ErDiagram` instance used by the resolver.

```python
# v3
class TaskResponse(DefineSubset):
    owner: Annotated[Optional[User], LoadBy('owner_id')] = None

# v4 — field name matches relationship name
class TaskResponse(DefineSubset):
    owner: Annotated[Optional[User], AutoLoad()] = None

# v4 — field name differs from relationship name
class TaskResponse(DefineSubset):
    author: Annotated[Optional[User], AutoLoad(origin='owner')] = None
```

```python
# v4 — diagram-bound AutoLoad factory (required)
diagram = BaseEntity.get_diagram()
AutoLoad = diagram.create_auto_load()
config_global_resolver(diagram)
```

`LoadBy` parameters `biz` and `origin_kls` are removed. Use `Relationship.name` and `AutoLoad(origin=...)` instead.

## 4. `MultipleRelationship` and `Link` removed

Multiple relationships to the same target entity are now expressed as separate `Relationship` entries, each with its own `name`, `loader`, and behavior.

```python
# v3
MultipleRelationship(
    field='user_id', target_kls=list[Task],
    links=[
        Link(biz='created', loader=created_loader, default_field_name='created_tasks'),
        Link(biz='assigned', loader=assigned_loader, default_field_name='assigned_tasks'),
    ]
)

# v4
Relationship(fk='user_id', target=list[Task], loader=created_loader, name='created_tasks'),
Relationship(fk='user_id', target=list[Task], loader=assigned_loader, name='assigned_tasks'),
```

## 5. Deprecated `Resolver` parameters removed

`loader_filters` and `global_loader_filter` (deprecated since v1.9.3) have been removed.

```python
# v3 (deprecated, with warning)
Resolver(loader_filters={...}, global_loader_filter={...})

# v4
Resolver(loader_params={...}, global_loader_param={...})
```

## 6. `field_fn` renamed to `fk_fn`

```python
# v3
Relationship(field='tags', target_kls=list[Tag], field_fn=lambda v: v.split(','))

# v4
Relationship(fk='tags', target=list[Tag], fk_fn=lambda v: v.split(','), name='tags')
```

## 7. `__pydantic_resolve_relationships__` removed

Use `__relationships__` only.

```python
# v3
class TaskEntity(BaseModel, BaseEntity):
    __pydantic_resolve_relationships__ = [...]

# v4
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [...]
```

## 8. `LoaderDepend` removed

Use `Loader` only.

## 9. `model_config` decorator removed

Use `serialization` only.

```python
# v3
from pydantic_resolve import model_config

@model_config()
class Data(BaseModel):
    hidden: str = Field(default='', exclude=True)
```

```python
# v4
from pydantic_resolve import serialization

@serialization
class Data(BaseModel):
    hidden: str = Field(default='', exclude=True)

schema = Data.model_json_schema(mode='serialization')
```

`serialization` recursively processes nested models, applies `exclude=True` handling, and sets `required` fields in serialization schema.