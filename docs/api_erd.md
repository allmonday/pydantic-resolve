# ER Diagram API

[中文版](./api_erd.zh.md)

## base_entity

```python
from pydantic_resolve import base_entity

BaseEntity = base_entity() -> type
```

Creates a base class that automatically collects `__relationships__` from subclasses. Call `BaseEntity.get_diagram()` to get the resulting `ErDiagram`.

```python
BaseEntity = base_entity()

class UserEntity(BaseModel, BaseEntity):
    id: int
    name: str

class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='owner_id', target=UserEntity, name='owner', loader=user_loader)
    ]
    id: int
    owner_id: int

diagram = BaseEntity.get_diagram()
```

## Relationship

```python
from pydantic_resolve import Relationship

Relationship(
    fk: str,
    target: Any,
    name: str,
    loader: Callable | None = None,
    fk_fn: Callable | None = None,
    fk_none_default: Any | None = None,
    fk_none_default_factory: Callable | None = None,
    load_many: bool = False,
    load_many_fn: Callable | None = None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `fk` | `str` | Foreign key field name on the entity |
| `target` | `Any` | Target entity class (or `list[Entity]` for to-many) |
| `name` | `str` | **Required.** Unique relationship name |
| `loader` | `Callable \| None` | DataLoader function |
| `fk_fn` | `Callable \| None` | Transform FK value before passing to loader |
| `fk_none_default` | `Any \| None` | Default value when FK is None |
| `fk_none_default_factory` | `Callable \| None` | Factory for default value when FK is None |
| `load_many` | `bool` | FK field contains multiple values |
| `load_many_fn` | `Callable \| None` | Transform FK field into iterable for load_many |

## Entity

```python
from pydantic_resolve import Entity

Entity(
    kls: type[BaseModel],
    relationships: list[Relationship] = [],
    queries: list[QueryConfig] = [],
    mutations: list[MutationConfig] = [],
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `kls` | `type[BaseModel]` | Pydantic model class |
| `relationships` | `list[Relationship]` | Outgoing relationships |
| `queries` | `list[QueryConfig]` | GraphQL query entry points |
| `mutations` | `list[MutationConfig]` | GraphQL mutation entry points |

## ErDiagram

```python
from pydantic_resolve import ErDiagram

ErDiagram(
    entities: list[Entity],
    description: str | None = None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `entities` | `list[Entity]` | All entity definitions |
| `description` | `str \| None` | Optional diagram description |

### add_relationship()

```python
merged = diagram.add_relationship(entities: list[Entity]) -> ErDiagram
```

Merges external entities (e.g., from ORM) into the diagram. Returns a new `ErDiagram`.

### External Diagram Ambiguity

`base_entity()` diagrams are scoped to a single model family, so relationship lookup is naturally unambiguous.

External diagrams are different. If the same model class appears in multiple external `ErDiagram` instances, and those diagrams define the same relationship `name` with different `fk` fields, `pydantic-resolve` now raises `ValueError` instead of silently picking the last registered diagram.

This matters when the library must infer relationship metadata outside the resolver-specific diagram, especially for:

- `DefineSubset` auto-adding hidden FK fields
- implicit relationship resolution by field name
- explicit `AutoLoad(origin=...)` on subset-only fields

Example of an ambiguous setup:

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

# Raises ValueError: ambiguous external ErDiagram relationship "user"
```

Use one of these patterns to avoid ambiguity:

- Prefer `base_entity()` + `BaseEntity.get_diagram()` when the models belong to one domain.
- Keep one authoritative external `ErDiagram` per model class and relationship name.
- If multiple external diagrams are unavoidable, do not reuse the same relationship `name` for different FK meanings on the same model class.
- In `DefineSubset`, explicitly include the FK field yourself if you do not want subset construction to infer it.

## AutoLoad

```python
AutoLoad(origin: str | None = None)
```

Annotation for auto-resolving fields via ERD relationships.

When the field name already matches `Relationship.name`, you usually do not need `AutoLoad()` at all:

```python
class TaskView(TaskEntity):
    owner: Optional[UserEntity] = None
```

Use `AutoLoad(origin=...)` only when the field name differs from the relationship name.

```python
class TaskView(TaskEntity):
    # explicit alias for relationship name `owner`
    my_owner: Annotated[Optional[UserEntity], AutoLoad(origin='owner')] = None

    # explicit alias for relationship name `tasks`
    items: Annotated[list[TaskEntity], AutoLoad(origin='tasks')] = []
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `origin` | `str \| None` | Relationship name to look up. Defaults to field name. |

## QueryConfig

```python
from pydantic_resolve import QueryConfig

QueryConfig(
    method: Callable,
    name: str | None = None,
    description: str | None = None,
)
```

## MutationConfig

```python
from pydantic_resolve import MutationConfig

MutationConfig(
    method: Callable,
    name: str | None = None,
    description: str | None = None,
)
```

## @query Decorator

Must be used as a method decorator **inside a Pydantic entity class**. It cannot decorate standalone functions.

```python
from pydantic_resolve import query

class SprintEntity(BaseModel, BaseEntity):
    id: int
    name: str

    @query
    async def get_all(cls, limit: int = 20) -> list['SprintEntity']:
        return await fetch_sprints(limit)
```

The GraphQL field name is generated automatically from entity name + method name.
Use `QueryConfig(name=...)` to override the method-name part when needed.

## @mutation Decorator

Must be used as a method decorator **inside a Pydantic entity class**. It cannot decorate standalone functions.

```python
from pydantic_resolve import mutation

class SprintEntity(BaseModel, BaseEntity):
    id: int
    name: str

    @mutation
    async def create(cls, name: str) -> 'SprintEntity':
        return await db.create_sprint(name=name)
```

The GraphQL field name is generated automatically from entity name + method name.
Use `MutationConfig(name=...)` to override the method-name part when needed.
