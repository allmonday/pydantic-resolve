# GraphQL API

[中文版](./api_graphql.zh.md)

## GraphQLHandler

```python
from pydantic_resolve.graphql import GraphQLHandler

handler = GraphQLHandler(
    er_diagram: ErDiagram,
    enable_from_attribute_in_type_adapter: bool = False,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `er_diagram` | `ErDiagram` | ERD to generate schema from |
| `enable_from_attribute_in_type_adapter` | `bool` | Enable Pydantic `from_attributes` mode |

### execute()

```python
result = await handler.execute(
    query: str,
) -> dict
```

Execute a GraphQL query string and return a GraphQL-style response dict.

```python
result = await handler.execute("""
{
    sprintEntityGetAll {
        id
        name
        tasks {
            id
            title
        }
    }
}
""")
```

The return value follows GraphQL response shape:

```python
{
    "data": {
        "sprintEntityGetAll": [...]
    },
    "errors": None,
}
```

## SchemaBuilder

```python
from pydantic_resolve.graphql import SchemaBuilder

builder = SchemaBuilder(er_diagram)
sdl = builder.build_schema()  # Returns the GraphQL SDL string
```

Low-level access to the generated GraphQL schema. Most users should use `GraphQLHandler` instead.

## @query

```python
from pydantic_resolve import query

class MyEntity(BaseModel, BaseEntity):
    @query
    async def get_all(cls, limit: int = 20) -> list['MyEntity']:
        return await fetch_items(limit)
```

Decorator that registers a method as a GraphQL query root field. Must be used inside a Pydantic entity class — it cannot decorate standalone functions.

The operation name is generated automatically from entity name + method name.
Use `QueryConfig(name=...)` when you need to override the method-name part of the generated GraphQL field.

## @mutation

```python
from pydantic_resolve import mutation

class MyEntity(BaseModel, BaseEntity):
    @mutation
    async def create(cls, name: str) -> 'MyEntity':
        return await create_item(name)
```

Decorator that registers a method as a GraphQL mutation root field. Must be used inside a Pydantic entity class — it cannot decorate standalone functions.

The operation name is generated automatically from entity name + method name.
Use `MutationConfig(name=...)` when you need to override the method-name part of the generated GraphQL field.

## QueryConfig

```python
from pydantic_resolve import QueryConfig

QueryConfig(
    method: Callable,
    name: str | None = None,
    description: str | None = None,
)
```

External alternative to `@query`. Define query functions outside entity classes and wire them into `Entity` via the `queries` list.

| Parameter | Type | Description |
|-----------|------|-------------|
| `method` | `Callable` | Async function. First argument is `cls`, followed by GraphQL arguments. |
| `name` | `str \| None` | Override for the method-name part of the generated GraphQL field. |
| `description` | `str \| None` | Field description in the generated schema. |

```python
async def get_all_sprints(cls, limit: int = 20) -> list[SprintEntity]:
    return [SprintEntity(**s) for s in SPRINTS[:limit]]

async def get_sprint_by_id(cls, id: int) -> SprintEntity | None:
    return SprintEntity(**SPRINTS.get(id, {}))

Entity(
    kls=SprintEntity,
    queries=[
        QueryConfig(method=get_all_sprints, name='sprints'),
        QueryConfig(method=get_sprint_by_id, name='sprint'),
    ],
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

External alternative to `@mutation`. Define mutation functions outside entity classes and wire them into `Entity` via the `mutations` list.

| Parameter | Type | Description |
|-----------|------|-------------|
| `method` | `Callable` | Async function. First argument is `cls`, followed by GraphQL arguments. |
| `name` | `str \| None` | Override for the method-name part of the generated GraphQL field. |
| `description` | `str \| None` | Field description in the generated schema. |

```python
async def create_sprint(cls, name: str) -> SprintEntity:
    sprint = await db.create_sprint(name=name)
    return SprintEntity.model_validate(sprint)

Entity(
    kls=SprintEntity,
    mutations=[
        MutationConfig(method=create_sprint, name='createSprint'),
    ],
)
```
