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
