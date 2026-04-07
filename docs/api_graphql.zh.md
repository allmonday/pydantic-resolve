# GraphQL API

[English](./api_graphql.md)

## GraphQLHandler

```python
from pydantic_resolve.graphql import GraphQLHandler

handler = GraphQLHandler(
    er_diagram: ErDiagram,
    enable_from_attribute_in_type_adapter: bool = False,
)
```

| 参数 | 类型 | 描述 |
|-----------|------|-------------|
| `er_diagram` | `ErDiagram` | 用于生成 schema 的 ERD |
| `enable_from_attribute_in_type_adapter` | `bool` | 启用 Pydantic 的 `from_attributes` 模式 |

### execute()

```python
result = await handler.execute(
    query: str,
    variables: dict | None = None,
) -> dict
```

执行 GraphQL 查询字符串并以字典形式返回结果。

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
schema = builder.build()  # 返回 GraphQL schema 对象
```

对生成的 GraphQL schema 的底层访问。大多数用户应该使用 `GraphQLHandler`。

## @query

```python
from pydantic_resolve import query

class MyEntity(BaseModel, BaseEntity):
    @query(name='items')
    async def get_all(cls, limit: int = 20) -> list['MyEntity']:
        return await fetch_items(limit)
```

将方法注册为 GraphQL 查询根字段的装饰器。

| 参数 | 类型 | 描述 |
|-----------|------|-------------|
| `name` | `str \| None` | GraphQL 字段名。默认为方法名。 |

## @mutation

```python
from pydantic_resolve import mutation

class MyEntity(BaseModel, BaseEntity):
    @mutation(name='createItem')
    async def create(cls, name: str) -> 'MyEntity':
        return await create_item(name)
```

将方法注册为 GraphQL 变更根字段的装饰器。
