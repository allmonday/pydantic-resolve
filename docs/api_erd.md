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

### create_auto_load()

```python
AutoLoad = diagram.create_auto_load() -> Callable
```

Creates an annotation factory bound to this diagram. Use in `Annotated` type hints.

### add_relationship()

```python
merged = diagram.add_relationship(entities: list[Entity]) -> ErDiagram
```

Merges external entities (e.g., from ORM) into the diagram. Returns a new `ErDiagram`.

## AutoLoad

```python
AutoLoad(origin: str | None = None)
```

Annotation for auto-resolving fields via ERD relationships.

```python
class TaskView(TaskEntity):
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
    # or with explicit relationship name:
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

    @query(name='sprints')
    async def get_all(cls, limit: int = 20) -> list['SprintEntity']:
        return await fetch_sprints(limit)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str \| None` | GraphQL field name. Defaults to method name. |

## @mutation Decorator

Must be used as a method decorator **inside a Pydantic entity class**. It cannot decorate standalone functions.

```python
from pydantic_resolve import mutation

class SprintEntity(BaseModel, BaseEntity):
    id: int
    name: str

    @mutation(name='createSprint')
    async def create(cls, name: str) -> 'SprintEntity':
        return await db.create_sprint(name=name)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str \| None` | GraphQL field name. Defaults to method name. |
