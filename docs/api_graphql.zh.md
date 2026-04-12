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
    context: dict[str, Any] | None = None,
) -> dict
```

执行 GraphQL 查询字符串，并返回 GraphQL 风格的响应字典。

| 参数 | 类型 | 描述 |
|-----------|------|-------------|
| `query` | `str` | GraphQL 查询字符串 |
| `context` | `dict \| None` | 请求级上下文，注入到 `@query`/`@mutation` 方法和下游 Resolver |

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

当提供 `context` 时，它在两处生效：

1. **`@query`/`@mutation` 方法** — 在方法签名中声明 `context` 参数即可直接接收。
2. **DataLoader** — context 会传入内部的 `Resolver(context=...)`，由 Resolver 自动注入到声明了 `_context` 属性的类式 DataLoader 中。

```python
# 使用 context 的 DataLoader
class TaskLoader(DataLoader):
    _context: dict  # 自动接收 Resolver context

    async def batch_load_fn(self, keys):
        user_id = self._context['user_id']
        tasks = await db.fetch_tasks_by_owner_and_ids(user_id, keys)
        ...
```

```python
# 从 FastAPI 端点传入上下文
result = await handler.execute(
    query=req.query,
    context={"user_id": current_user.id},
)
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
如果你需要覆盖生成字段中的"方法名部分"，请使用 `QueryConfig(name=...)`。

### 接收请求上下文

添加 `context` 参数可接收框架级数据（如来自 JWT 的 `user_id`）。该参数**对 GraphQL schema 不可见** — 客户端无法看到或设置它。

```python
class MyEntity(BaseModel, BaseEntity):
    @query
    async def get_my_items(cls, limit: int = 20, context: dict = None) -> list['MyEntity']:
        user_id = context['user_id']
        return await fetch_items_by_owner(user_id, limit)
```

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

async def get_my_sprints(cls, limit: int = 20, context: dict = None) -> list[SprintEntity]:
    user_id = context['user_id']
    return await fetch_sprints_by_owner(user_id, limit)

Entity(
    kls=SprintEntity,
    queries=[
        QueryConfig(method=get_all_sprints, name='sprints'),
        QueryConfig(method=get_sprint_by_id, name='sprint'),
        QueryConfig(method=get_my_sprints, name='my_sprints'),
    ],
)
```

与 `@query` 相同，`QueryConfig` 方法也可以声明 `context` 参数。它**对 GraphQL schema 不可见**，由 `handler.execute(context=...)` 注入。

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
