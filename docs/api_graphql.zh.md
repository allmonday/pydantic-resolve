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
) -> dict
```

执行 GraphQL 查询字符串，并返回 GraphQL 风格的响应字典。

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

返回值遵循 GraphQL 响应结构：

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
sdl = builder.build_schema()  # 返回 GraphQL SDL 字符串
```

对生成的 GraphQL schema 的底层访问。大多数用户应该使用 `GraphQLHandler`。

## @query

```python
from pydantic_resolve import query

class MyEntity(BaseModel, BaseEntity):
    @query
    async def get_all(cls, limit: int = 20) -> list['MyEntity']:
        return await fetch_items(limit)
```

将方法注册为 GraphQL 查询根字段的装饰器。必须用在 Pydantic 实体类内部，不能装饰独立函数。

操作名会根据实体名和方法名自动生成。
如果你需要覆盖生成字段中的“方法名部分”，请使用 `QueryConfig(name=...)`。

## @mutation

```python
from pydantic_resolve import mutation

class MyEntity(BaseModel, BaseEntity):
    @mutation
    async def create(cls, name: str) -> 'MyEntity':
        return await create_item(name)
```

将方法注册为 GraphQL 变更根字段的装饰器。必须用在 Pydantic 实体类内部，不能装饰独立函数。

操作名会根据实体名和方法名自动生成。
如果你需要覆盖生成字段中的“方法名部分”，请使用 `MutationConfig(name=...)`。

## QueryConfig

```python
from pydantic_resolve import QueryConfig

QueryConfig(
    method: Callable,
    name: str | None = None,
    description: str | None = None,
)
```

`@query` 的外部替代方案。在实体类之外定义查询函数，通过 `Entity` 的 `queries` 列表接入。

| 参数 | 类型 | 描述 |
|-----------|------|-------------|
| `method` | `Callable` | 异步函数。第一个参数是 `cls`，后面是 GraphQL 参数。 |
| `name` | `str \| None` | 覆盖生成 GraphQL 字段中的方法名部分。 |
| `description` | `str \| None` | 生成 schema 中的字段描述。 |

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

`@mutation` 的外部替代方案。在实体类之外定义变更函数，通过 `Entity` 的 `mutations` 列表接入。

| 参数 | 类型 | 描述 |
|-----------|------|-------------|
| `method` | `Callable` | 异步函数。第一个参数是 `cls`，后面是 GraphQL 参数。 |
| `name` | `str \| None` | 覆盖生成 GraphQL 字段中的方法名部分。 |
| `description` | `str \| None` | 生成 schema 中的字段描述。 |

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
