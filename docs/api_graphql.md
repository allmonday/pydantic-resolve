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
    variables: dict | None = None,
) -> dict
```

Execute a GraphQL query string and return the result as a dict.

```python
result = await handler.execute("""
{
    sprints {
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

## SchemaBuilder

```python
from pydantic_resolve.graphql import SchemaBuilder

builder = SchemaBuilder(er_diagram)
schema = builder.build()  # Returns a GraphQL schema object
```

Low-level access to the generated GraphQL schema. Most users should use `GraphQLHandler` instead.

## @query

```python
from pydantic_resolve import query

class MyEntity(BaseModel, BaseEntity):
    @query(name='items')
    async def get_all(cls, limit: int = 20) -> list['MyEntity']:
        return await fetch_items(limit)
```

Decorator that registers a method as a GraphQL query root field.

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str \| None` | GraphQL field name. Defaults to method name. |

## @mutation

```python
from pydantic_resolve import mutation

class MyEntity(BaseModel, BaseEntity):
    @mutation(name='createItem')
    async def create(cls, name: str) -> 'MyEntity':
        return await create_item(name)
```

Decorator that registers a method as a GraphQL mutation root field.
