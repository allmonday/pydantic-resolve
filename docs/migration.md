---
description: Migration guide across pydantic-resolve versions. Covers v5 → v6 (grouped entity GraphQL layout) and earlier breaking changes, with before/after code for each.
---

# Migration Guide

## v5 to v6

v6 groups entity `@query` / `@mutation` operations by entity under `{Entity}Query` / `{Entity}Mutation` types. The Python surface — `Entity`, the `@query` / `@mutation` decorators, `GraphQLHandler` — is unchanged; only the generated GraphQL schema, the response shape, and the MCP schema tools change. Four breaking changes affect GraphQL clients and MCP consumers.

### 1. Operations are grouped by entity

Each entity's `@query` / `@mutation` methods are now fields on a `{Entity}Query` / `{Entity}Mutation` group OBJECT, and the root `Query` / `Mutation` mounts one NON_NULL field per entity. Method names are used verbatim — the old `entityPrefix + MethodCamel` camelCase is gone.

```graphql
# v5 — flat root field per method
type Query {
  userEntityGetAll(limit: Int): [UserEntity!]!
  userEntityGetById(id: Int!): UserEntity
}

# v6 — one group per entity, method names verbatim
type Query {
  UserEntity: UserEntityQuery!
}

type UserEntityQuery {
  get_all(limit: Int): [UserEntity!]!
  get_by_id(id: Int!): UserEntity
}
```

Client queries add one nesting level (the entity group):

```graphql
# v5
{ userEntityGetAll(limit: 10) { id name } }

# v6
{ UserEntity { get_all(limit: 10) { id name } } }
```

Error reporting improves alongside this: selecting a bare group with no method (`{ UserEntity }`) returns a `BARE_GROUP_FIELD` error listing the available methods, and unknown group / method errors carry a GraphQL `path` (e.g. `["UserEntity", "get_all"]`). A schema with no `@query` methods now omits the root `Query` type entirely (introspection reports `queryType: null`).

### 2. Response data is nested per entity

Dispatch is now two-level (group → method), so results nest as `data[entity][method]`.

```python
# v5
users = result["data"]["userEntityGetAll"]

# v6
users = result["data"]["UserEntity"]["get_all"]
```

Mutations nest the same way: `result["data"]["UserEntity"]["create_user"]`.

### 3. MCP schema tools take `entity` + `method`

`get_query_schema` / `get_mutation_schema` replace the single `name` argument with `entity` and `method`. `list_queries` / `list_mutations` now return one entry per method — `{entity, method, name ("<entity>.<method>"), description}` — so identifiers stay unique when two entities share a method name.

```python
# v5
get_query_schema(name="userEntityGetAll", app_name="blog")
queries = list_queries(app_name="blog")
# -> [{"name": "userEntityGetAll", "description": "..."}]

# v6
get_query_schema(entity="UserEntity", method="get_all", app_name="blog")
queries = list_queries(app_name="blog")
# -> [{"entity": "UserEntity", "method": "get_all",
#      "name": "UserEntity.get_all", "description": "..."}]
```

### 4. Removed naming utilities

`pydantic_resolve/graphql/utils/naming.py` (`to_camel_case`, `to_graphql_field_name`) is removed — field names are the verbatim method name now, so the camelCase + entity-prefix logic is obsolete. The only naming helper left is `group_type_name(entity_name, suffix)` in `pydantic_resolve/graphql/utils/__init__.py`. If you imported the old helpers, switch to `group_type_name` or inline the verbatim name.

## v5.4 to v5.5

v5.5 simplifies the AutoLoad API and adds implicit relationship resolution. Two breaking changes affect code that uses ER Diagram.

### 1. `diagram.create_auto_load()` replaced by standalone `AutoLoad()`

The diagram-bound factory is removed. `AutoLoad` is now a direct import from `pydantic_resolve`.

```python
# v5.4
diagram = BaseEntity.get_diagram()
AutoLoad = diagram.create_auto_load()       # factory bound to diagram
config_global_resolver(diagram)

class TaskView(TaskEntity):
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None

# v5.5
from pydantic_resolve import AutoLoad       # standalone import

class TaskView(TaskEntity):
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
```

The `config_global_resolver(diagram)` or `config_resolver(...)` call is still required — it tells the resolver which diagram to use for relationship lookup.

### 2. Implicit AutoLoad (no annotation needed for matching names)

When a field name matches a relationship `name`, the resolver automatically generates the resolve method. No `AutoLoad()` annotation is required.

```python
# v5.4 — explicit annotation required
class TaskView(TaskEntity):
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None

# v5.5 — implicit when name matches
class TaskView(TaskEntity):
    owner: Optional[UserEntity] = None       # auto-resolved via relationship name 'owner'
```

Explicit `AutoLoad(origin=...)` is still needed when the field name differs from the relationship name:

```python
class TaskView(TaskEntity):
    my_owner: Annotated[Optional[UserEntity], AutoLoad(origin='owner')] = None
```

### 3. `LoaderInfo._er_configs_map` removed

This internal field was previously set by `create_auto_load()`. If you were directly accessing it, switch to using the relationship lookup via the diagram or `config_resolver`.

### 4. External `ErDiagram` ambiguity is now explicit

In v5.5, `AutoLoad()` is no longer bound to one diagram instance. That simplifies regular usage, but it also means some setup-time inference must look up relationship metadata by model class and relationship name.

For `base_entity()` diagrams, this is still unambiguous because one model family has one authoritative diagram.

For external `ErDiagram(...)` definitions, ambiguity can appear if multiple diagrams register the same model class with the same relationship `name` but different `fk` values. In that case, `pydantic-resolve` now raises `ValueError` instead of silently using the last registration.

This most commonly appears in `DefineSubset` when hidden FK fields must be auto-added:

```python
ErDiagram(entities=[
    Entity(kls=TaskEntity, relationships=[
        Relationship(fk='owner_id', target=UserEntity, name='user', loader=user_loader),
    ])
])

ErDiagram(entities=[
    Entity(kls=TaskEntity, relationships=[
        Relationship(fk='manager_id', target=UserEntity, name='user', loader=user_loader),
    ])
])

class TaskSummary(DefineSubset):
    __subset__ = (TaskEntity, ('id',))
    user: Optional[UserEntity] = None

# v5.5+: raises ValueError instead of silently picking one FK
```

Recommended migration path:

- Prefer `base_entity()` for one domain model family.
- Keep one authoritative external ER definition per `(model class, relationship name)`.
- If you intentionally need different meanings, give them different relationship names.
- If subset construction should not infer the FK automatically, include the FK field explicitly in the subset.

---

## v4 to v5

v5.0 introduces one breaking rename. New features (ORM integration, GraphiQL, MCP schema) are additive and documented separately.

### 1. `ErDiagram.configs` → `ErDiagram.entities`

The `ErDiagram` constructor parameter is renamed from `configs` to `entities`.

```python
# v4
diagram = ErDiagram(configs=[
    Entity(kls=User, relationships=[...]),
])

# v5
diagram = ErDiagram(entities=[
    Entity(kls=User, relationships=[...]),
])
```

If you use `base_entity()` with `__relationships__`, no change is needed — `get_diagram()` is updated internally.

### 2. Forward references can use module-path syntax

If you previously relied on same-module ordering or local `setattr(...)` workarounds for ER Diagram targets, you can now write forward refs as `'package.module:ClassName'`.

```python
Relationship(fk='owner_id', target='app.dto.user:UserDTO', name='owner')
Relationship(fk='id', target=list['app.dto.post:PostDTO'], name='posts')
```

This is optional and backward compatible.

---

## v3 to v4

v4.0 introduces breaking changes to the ER Diagram API, simplifying how relationships are defined.

### 1. Relationship parameter renames

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

### 2. Relationship `name` is now required (replaces `default_field_name`)

`name` is the unique identifier for each relationship. It serves as the GraphQL field name and the lookup key for `AutoLoad`.

```python
# v3: default_field_name was optional
Relationship(field='owner_id', target_kls=User, loader=user_loader, default_field_name='owner')

# v4: name is required
Relationship(fk='owner_id', target=User, loader=user_loader, name='owner')
```

### 3. `LoadBy` replaced by `AutoLoad`

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

### 4. `MultipleRelationship` and `Link` removed

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

### 5. Deprecated `Resolver` parameters removed

`loader_filters` and `global_loader_filter` (deprecated since v1.9.3) have been removed.

```python
# v3 (deprecated, with warning)
Resolver(loader_filters={...}, global_loader_filter={...})

# v4
Resolver(loader_params={...}, global_loader_param={...})
```

### 6. `field_fn` renamed to `fk_fn`

```python
# v3
Relationship(field='tags', target_kls=list[Tag], field_fn=lambda v: v.split(','))

# v4
Relationship(fk='tags', target=list[Tag], fk_fn=lambda v: v.split(','), name='tags')
```

### 7. `__pydantic_resolve_relationships__` removed

Use `__relationships__` only.

```python
# v3
class TaskEntity(BaseModel, BaseEntity):
    __pydantic_resolve_relationships__ = [...]

# v4
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [...]
```

### 8. `LoaderDepend` removed

Use `Loader` only.

### 9. `model_config` decorator removed

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
