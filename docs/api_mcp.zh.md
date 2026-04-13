# MCP API

[English](./api_mcp.md)

## create_mcp_server

```python
from pydantic_resolve import create_mcp_server

mcp = create_mcp_server(
    apps: list[AppConfig],
    name: str = "Pydantic-Resolve GraphQL API",
) -> "FastMCP"
```

创建一个暴露多个 ErDiagram 应用的 MCP 服务器。

| 参数 | 类型 | 描述 |
|-----------|------|-------------|
| `apps` | `list[AppConfig]` | 应用配置 |
| `name` | `str` | MCP 服务器名称（默认：`"Pydantic-Resolve GraphQL API"`） |

返回配置好的 `FastMCP` 服务器实例。

```python
mcp = create_mcp_server(
    apps=[AppConfig(name="blog", er_diagram=diagram)]
)
mcp.run(transport="streamable-http", port=8080)
```

## AppConfig

```python
from pydantic_resolve import AppConfig

AppConfig(
    name: str,
    er_diagram: ErDiagram,
    description: str | None = None,
    query_description: str | None = None,
    mutation_description: str | None = None,
    enable_from_attribute_in_type_adapter: bool = False,
    context_extractor: Callable | None = None,
)
```

| 参数 | 类型 | 描述 |
|-----------|------|-------------|
| `name` | `str` | 应用名称（必填） |
| `er_diagram` | `ErDiagram` | ErDiagram 实例（必填） |
| `description` | `str \| None` | 供 AI 代理使用的应用描述 |
| `query_description` | `str \| None` | Query 类型的描述 |
| `mutation_description` | `str \| None` | Mutation 类型的描述 |
| `enable_from_attribute_in_type_adapter` | `bool` | 启用 Pydantic 的 from_attributes 模式 |
| `context_extractor` | `Callable \| None` | 从 HTTP 请求提取上下文的回调函数 |

### context_extractor

可选的回调函数，用于从 MCP 的 HTTP 请求中提取请求级上下文（如用户身份），并传递给 `handler.execute(context=...)`，最终注入到 `@query`/`@mutation` 方法的 `_context` 参数。

函数签名：`(Context) -> dict | Awaitable[dict]`，支持同步和异步。

```python
from fastmcp.server.context import Context
from fastmcp.server.dependencies import get_http_headers

def extract_user_context(ctx: Context) -> dict:
    # 注意：get_http_headers() 默认会过滤 authorization 等敏感头，
    # 必须通过 include 参数显式声明才能获取。
    headers = get_http_headers(include={"authorization"})
    auth = headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        # 生产环境中应解码 JWT，此处仅为演示
        return {"user_id": int(token)}
    return {}

apps = [
    AppConfig(
        name="blog",
        er_diagram=diagram,
        context_extractor=extract_user_context,
    ),
]
```

数据流向：

```
HTTP 请求 (Authorization: Bearer <token>)
  → FastMCP Context
    → context_extractor(ctx) → {"user_id": 1}
      → handler.execute(query, context={"user_id": 1})
        → @query 方法的 _context 参数
```

**注意事项：**

- `get_http_headers()` 默认排除 `authorization`、`content-type` 等头。必须传入 `include={"authorization"}` 才能获取。
- 如果 MCP 通过 stdio 传输（无 HTTP 请求），`get_http_headers()` 返回空字典。
- 不配置 `context_extractor` 时，行为与之前完全一致（不传 context）。

## MultiAppManager

用于处理多个应用配置的内部管理器。由 `create_mcp_server` 内部使用。

## 渐进式披露工具

MCP 服务器自动注册这些工具：

| 工具 | 层级 | 描述 |
|------|-------|-------------|
| `list_apps` | 0 | 发现可用的应用 |
| `list_queries` | 1 | 列出应用的查询 |
| `list_mutations` | 1 | 列出应用的变更 |
| `get_query_schema` | 2 | 获取详细的查询 schema |
| `get_mutation_schema` | 2 | 获取详细的变更 schema |
| `graphql_query` | 3 | 执行 GraphQL 查询 |
| `graphql_mutation` | 3 | 执行 GraphQL 变更 |
