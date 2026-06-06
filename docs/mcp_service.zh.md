# MCP 服务

[English](./mcp_service.md)

MCP（Model Context Protocol）支持让 AI 代理通过渐进式发现来探索和查询你的 GraphQL API。它基于与 `AutoLoad` 和 `GraphQLHandler` 相同的 ERD 构建。

## 安装

```bash
pip install pydantic-resolve[mcp]
```

## 目标

你有一个包含实体和关系的 ERD。你想将它暴露为 MCP 服务，让 AI 代理可以发现和查询你的数据 —— 不需要写 GraphQL schema 或 resolver：

```
代理: "列出 Alice 的所有文章"
  → MCP 服务器转换为 GraphQL 查询
  → ERD 解析关系
  → 代理收到结果
```

## Step 1：创建 MCP 服务器

```python
from pydantic_resolve import AppConfig, create_mcp_server

mcp = create_mcp_server(
    apps=[
        AppConfig(name="blog", er_diagram=diagram),  # (1)
    ]
)

mcp.run()  # (2)
```

1.  `AppConfig` 将你的 ERD 绑定到一个命名端点。`name` 用于标识应用。
2.  默认传输方式是 `stdio`（用于 Claude Desktop）。使用 `transport="streamable-http"` 用于基于 Web 的代理。

## Step 2：提供多个应用

一个 MCP 服务器可以暴露多个 ERD：

```python
mcp = create_mcp_server(
    apps=[
        AppConfig(
            name="blog",
            er_diagram=blog_diagram,
            description="带有用户和文章的博客系统",
        ),
        AppConfig(
            name="shop",
            er_diagram=shop_diagram,
            description="带有产品和订单的电子商务系统",
        ),
    ],
    name="My API",
)

mcp.run(transport="streamable-http", port=8080)
```

## 渐进式发现

MCP 服务器分层暴露信息，AI 代理可以逐步探索：

```
Layer 0: list_apps          → "有哪些应用可用？"
Layer 1: list_queries       → "此应用支持哪些查询？"
Layer 2: get_query_schema   → "此查询有哪些字段和参数？"
Layer 3: graphql_query      → "执行此 GraphQL 查询"
```

示例流程：

1. 代理调用 `list_apps` → 发现 `["blog", "shop"]`
2. 代理为 `blog` 调用 `list_queries` → 发现 `["users", "posts", "createPost"]`
3. 代理为 `users` 调用 `get_query_schema` → 查看可用字段和参数
4. 代理调用 `graphql_query` → 执行 `{ users { id name posts { title } } }`

## 传输模式

```python
# HTTP 传输（推荐用于基于 Web 的代理）
mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)

# SSE（Server-Sent Events）传输
mcp.run(transport="sse", port=8080)

# stdio 传输（用于 Claude Desktop 集成）
mcp.run(transport="stdio")
```

| 参数 | 描述 | 默认值 |
|-----------|-------------|---------|
| `transport` | 传输模式：`"stdio"`、`"streamable-http"`、`"sse"` | `"stdio"` |
| `host` | 绑定的主机地址 | `"127.0.0.1"` |
| `port` | 端口号 | `"8000"` |

## AppConfig 参数

| 参数 | 类型 | 必需 | 描述 |
|-----------|------|----------|-------------|
| `name` | `str` | 是 | 应用名称，标识 GraphQL 端点 |
| `er_diagram` | `ErDiagram` | 是 | 带有实体定义的 ErDiagram 实例 |
| `description` | `str \| None` | 否 | 给 AI 代理的应用描述 |
| `query_description` | `str \| None` | 否 | Query 类型的描述 |
| `mutation_description` | `str \| None` | 否 | Mutation 类型的描述 |
| `enable_from_attribute_in_type_adapter` | `bool` | 否 | 启用 Pydantic from_attributes 模式（默认：False） |

!!! note
    `create_mcp_server()` 会在内部创建隔离的 GraphQL handler，因此这套配置本身不需要 `config_global_resolver(diagram)`，除非你还打算在别处直接调用 `Resolver()`。

## 下一步

- [API 参考](./api_mcp.zh.md) 了解详细的 MCP API 签名
- [GraphQL 指南](./graphql_guide.zh.md) 了解更多 GraphQL 设置
