# UseCase MCP API

[English](./api_use_case_mcp.md)

## create_use_case_mcp_server

```python
from pydantic_resolve.use_case import create_use_case_mcp_server

mcp = create_use_case_mcp_server(
    apps: list[UseCaseAppConfig],
    name: str = "Pydantic-Resolve UseCase API",
) -> "FastMCP"
```

创建一个 MCP 服务，通过渐进式发现将 `UseCaseService` 方法暴露给 AI agent。

| 参数 | 类型 | 说明 |
|------|------|------|
| `apps` | `list[UseCaseAppConfig]` | 应用配置列表 |
| `name` | `str` | MCP 服务名称（默认：`"Pydantic-Resolve UseCase API"`） |

返回配置好的 `FastMCP` 服务实例。

```python
mcp = create_use_case_mcp_server(
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
    context_extractor: Callable | None = None,
)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 应用名称（必填） |
| `services` | `list[type[UseCaseService]]` | UseCaseService 子类列表（必填） |
| `description` | `str \| None` | 应用描述，供 AI agent 参考 |
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
      → call_use_case 将 context 合并到 kwargs
        → TaskService.get_my_tasks(user_id=1)
```

**注意：** `get_http_headers()` 默认会过滤 `authorization`、`content-type` 等敏感头。必须传入 `include={"authorization"}` 才能获取 Authorization 头。当 MCP 通过 stdio 传输运行时（无 HTTP 请求），`get_http_headers()` 返回空 dict。

## UseCaseService

```python
from pydantic_resolve.use_case import UseCaseService

class MyService(UseCaseService):
    """服务描述（AI agent 可见）。"""

    @classmethod
    async def my_method(cls, param1: int) -> MyDTO:
        """方法描述（AI agent 可见）。"""
        ...
```

业务服务的基类。`BusinessMeta` 元类会自动发现 `async classmethod` 定义并存储供内省使用。

**约定：**

- 方法必须是 `@classmethod` + `async`
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

标记方法参数应从 `context_extractor` 获取值，而非从 MCP 工具的 `params` JSON 传入。方法签名在 FastAPI（直接传参）和 MCP（从上下文注入）中保持一致。

```python
class TaskService(UseCaseService):
    @classmethod
    async def get_my_tasks(
        cls,
        user_id: Annotated[int, FromContext()],
    ) -> list[TaskSummary]:
        ...
```

- 如果 context 中存在该 key，会注入到方法调用中
- 如果 context 中不存在且参数无默认值，返回错误
- 如果 context 中不存在但参数有默认值，使用默认值

## 渐进式发现工具

MCP 服务自动注册以下工具：

| 工具 | 层级 | 说明 |
|------|------|------|
| `list_apps` | 0 | 发现可用应用 |
| `list_services` | 1 | 列出应用中的服务 |
| `describe_service` | 2 | 获取方法签名、参数 schema 和 DTO 类型定义 |
| `call_use_case` | 3 | 执行指定方法 |

### call_use_case

```python
call_use_case(
    app_name: str,
    service_name: str,
    method_name: str,
    params: str = "{}",
)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `app_name` | `str` | 应用名称（来自 `list_apps`） |
| `service_name` | `str` | 服务名称（来自 `list_services`） |
| `method_name` | `str` | 方法名称（来自 `describe_service`） |
| `params` | `str` | 方法参数的 JSON 字符串（默认：`"{}"`） |

`params` 字符串会被解析为 JSON 并作为关键字参数传给方法。标注了 `FromContext` 的参数从 context_extractor 结果中注入，不从 `params` 获取。
