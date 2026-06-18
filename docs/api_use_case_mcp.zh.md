# UseCase MCP API

[English](./api_use_case_mcp.md)

## create_use_case_graphql_mcp_server

```python
from pydantic_resolve.use_case import create_use_case_graphql_mcp_server

mcp = create_use_case_graphql_mcp_server(
    apps: list[UseCaseAppConfig],
    name: str = "Pydantic-Resolve UseCase GraphQL API",
) -> "FastMCP"
```

创建一个 MCP 服务，通过 4 层渐进式发现将 `UseCaseService` 方法暴露给 AI agent，数据层使用 GraphQL 字符串风格。

| 参数 | 类型 | 说明 |
|------|------|------|
| `apps` | `list[UseCaseAppConfig]` | 应用配置列表 |
| `name` | `str` | MCP 服务名称（默认：`"Pydantic-Resolve UseCase GraphQL API"`） |

返回配置好的 `FastMCP` 服务实例。

```python
mcp = create_use_case_graphql_mcp_server(
    apps=[UseCaseAppConfig(name="project", services=[TaskService])]
)
mcp.run(transport="streamable-http", port=8080)
```

## UseCaseAppConfig

```python
from pydantic_resolve.use_case import UseCaseAppConfig

UseCaseAppConfig(
    name: str,
    services: list[type[UseCaseService]],
    description: str | None = None,
    enable_mutation: bool = True,
    context_extractor: Callable | None = None,
)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 应用名称（必填） |
| `services` | `list[type[UseCaseService]]` | UseCaseService 子类列表（必填） |
| `description` | `str \| None` | 应用描述，供 AI agent 参考 |
| `enable_mutation` | `bool` | mutation 方法是否在 MCP 中可见（默认：`True`） |
| `context_extractor` | `Callable \| None` | 从请求中提取上下文的回调函数 |

### context_extractor

可选的回调函数，从 MCP HTTP 请求中提取请求级上下文（如 Authorization 头中的用户身份）。提取的 dict 会合并到方法 kwargs 中，供 `FromContext` 标注的参数使用。

签名：`(Context) -> dict | Awaitable[dict]`，支持同步和异步。

```python
from fastmcp.server.context import Context
from fastmcp.server.dependencies import get_http_headers

def extract_user_context(ctx: Context) -> dict:
    headers = get_http_headers(include={"authorization"})
    auth = headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        return {"user_id": int(token)}
    return {}

apps = [
    UseCaseAppConfig(
        name="project",
        services=[TaskService],
        context_extractor=extract_user_context,
    ),
]
```

数据流：

```
HTTP 请求 (Authorization: Bearer <token>)
  → FastMCP Context
    → context_extractor(ctx) → {"user_id": 1}
      → 方法调用时将 context 合并到 kwargs
        → TaskService.get_my_tasks(user_id=1)
```

**注意：** `get_http_headers()` 默认会过滤 `authorization`、`content-type` 等敏感头。必须传入 `include={"authorization"}` 才能获取 Authorization 头。当 MCP 通过 stdio 传输运行时（无 HTTP 请求），`get_http_headers()` 返回空 dict。

## UseCaseService

```python
from pydantic_resolve.use_case import UseCaseService
from pydantic_resolve import query, mutation

class MyService(UseCaseService):
    """服务描述（AI agent 可见）。"""

    @query
    async def my_method(cls, param1: int) -> MyDTO:
        """方法描述（AI agent 可见）。"""
        ...
```

业务服务的基类。`BusinessMeta` 元类会自动发现被 `@query` 或 `@mutation` 装饰的方法并存储供内省使用。

**约定：**

- 方法必须使用 `@query` 或 `@mutation` 装饰器（来自 `pydantic_resolve`）
- 方法必须是 `async`
- 私有方法（以 `_` 开头）和 `get_tag_name` 会被排除
- 类和方法的 docstring 会作为描述展示给 AI agent
- 返回类型注解用于 SDL 类型生成

### get_tag_name

```python
@classmethod
def get_tag_name(cls) -> str
```

默认返回类名。可重写以自定义 FastAPI 中使用的 OpenAPI tag 名称：

```python
class TaskService(UseCaseService):
    @classmethod
    def get_tag_name(cls):
        return "任务"

# FastAPI 中使用
@app.get("/tasks", tags=[TaskService.get_tag_name()])
```

## FromContext

```python
from typing import Annotated
from pydantic_resolve.use_case import FromContext

user_id: Annotated[int, FromContext()]
```

标记方法参数应从 `context_extractor` 获取值，而非从 GraphQL 查询传入。方法签名在 FastAPI（直接传参）和 MCP（从上下文注入）中保持一致。

```python
class TaskService(UseCaseService):
    @query
    async def get_my_tasks(
        cls,
        user_id: Annotated[int, FromContext()],
    ) -> list[TaskSummary]:
        ...
```

- 如果 context 中存在该 key，会注入到方法调用中
- 如果 context 中不存在且参数无默认值，返回错误
- 如果 context 中不存在但参数有默认值，使用默认值
- `FromContext` 参数不能通过 GraphQL 查询参数传入

## 渐进式发现工具

MCP 服务注册四个工具，构成一个发现漏斗：从便宜的广度扫描到昂贵的精确查询。

| 工具 | 层级 | 说明 |
|------|------|------|
| `list_apps` | 1 | 廉价的应用发现 — 名称 + 服务数量 |
| `describe_compose_schema` | 2 | 单应用的 service + method 列表（不含参数 / 类型 / DTO 字段） |
| `describe_compose_method` | 3 | 单方法的详细信息：参数、返回类型，以及包含完整类型树的 SDL 字符串 |
| `compose_query` | 4 | 对 compose surface 执行 GraphQL 数据查询 |

漏斗故意推迟详细类型信息的加载，直到 agent 选定具体方法。Schema 发现走 Layer 2 + 3 —— `compose_query` 拒绝 GraphQL introspection（`__schema`、`__type`、`__typename`），并指向 `describe_compose_schema`。

### list_apps

```python
list_apps() -> dict
```

返回所有已配置应用的元数据。

```python
{
  "success": True,
  "data": [
    {"name": "project", "description": "...", "services_count": 3}
  ],
  "hint": "Use describe_compose_schema(app_name='project') ..."
}
```

### describe_compose_schema

```python
describe_compose_schema(app_name: str) -> dict
```

列出某个应用下的 services 与 methods。紧凑格式：仅名称 + 类型 + 描述。当 app 配置了 `enable_mutation=False` 时 mutation 会被过滤掉。

```python
{
  "success": True,
  "data": {
    "services": {
      "TaskService": {
        "description": "Task management service.",
        "methods": [
          {"name": "list_tasks", "kind": "query", "description": "Get all tasks."},
          {"name": "get_task", "kind": "query", "description": "Get a task by ID."}
        ]
      }
    }
  },
  "hint": "Use describe_compose_method(app_name='project', service_name='TaskService', method_name='get_task') ..."
}
```

### describe_compose_method

```python
describe_compose_method(
    app_name: str,
    service_name: str,
    method_name: str,
) -> dict
```

返回单个方法的详细信息：参数（含类型 + 默认值）、返回类型，以及 `sdl` 字符串。`sdl` 以方法签名注释作为头部，后跟返回 DTO 及其可达的所有嵌套 DTO 的完整类型定义。在拼装 query 之前，可将其作为字段名的唯一真相来源 —— 顶层和嵌套字段都在里面。

```python
{
  "success": True,
  "data": {
    "name": "get_task",
    "kind": "query",
    "description": "Get a task by ID.",
    "args": [{"name": "task_id", "type": "int"}],
    "returns": "TaskSummary",
    "sdl": "# TaskService.get_task(task_id: Int): TaskSummary\n\ntype TaskSummary {\n  id: Int!\n  title: String!\n  owner: UserSummary\n}\n\ntype UserSummary {\n  id: Int!\n  name: String!\n}"
  },
  "hint": "Use compose_query(app_name='project', query='{ TaskService { get_task(task_id: 1) { title } } }') ..."
}
```

### compose_query

```python
compose_query(
    app_name: str,
    query: str,
) -> dict
```

对 compose surface 执行 GraphQL 数据查询。固定 3 层结构：`Query → Service → Method → DTO 字段选择`。适用于在单次请求中跨 service 拉取相关数据。

**规则：**

- 不允许别名（GraphQL 的 `field:` 语法）。每个字段名在父级作用域内必须唯一。
- Service / method 名必须匹配 schema。用 `describe_compose_schema` 发现可用名称。
- 方法参数写在 method 字段的圆括号里：`get_sprint(sprint_id: 1)`。
- 标注了 `FromContext` 的参数是服务端注入的，不能从查询参数传入。
- method 之下的 DTO 字段选择投影到该方法的返回 DTO。嵌套 DTO 需要子选择；如果选错子字段，错误响应会列出该 DTO 的可用字段。
- mutation 方法要求 app 配置 `enable_mutation=True`。
- introspection 查询（`__schema` / `__type` / `__typename`）会被拒绝 —— 改用 `describe_compose_schema`。

**执行语义：**

- `@query` 方法并发执行。
- `@mutation` 方法按声明顺序串行执行。
- 单次 `compose_query` 调用内 query 和 mutation 之间的相对顺序不保证。如需「先创建后读取」的语义，请拆成两次调用。

**响应结构**与请求镜像：每个 Service 是一个 key，value 是 method-name → result 的 dict。

```python
compose_query(
    app_name="project",
    query='''
    {
      SprintService {
        list_sprints { id name }
        get_sprint(sprint_id: 1) { name }
      }
      TaskService {
        get_task(task_id: 1) { title owner_id }
      }
    }
    ''',
)
```

失败时：`success=False`，`error`，`error_type`（取值之一：`validation_error`、`type_not_found`、`operation_not_found`、`query_execution_error`、`mutation_execution_error`、`app_not_found`、`internal_error`）。
