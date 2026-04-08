# MCP 服务

[English](./mcp_service.md)

MCP（Model Context Protocol）支持让 AI 代理通过渐进式发现来发现和与你的 GraphQL API 交互。它基于与 `AutoLoad` 和 `GraphQLHandler` 相同的 ERD 构建。

## 安装

```bash
pip install pydantic-resolve[mcp]
```

## 快速开始

```python
from pydantic_resolve import AppConfig, create_mcp_server

# diagram 是你配置的 ErDiagram
mcp = create_mcp_server(
    apps=[AppConfig(name="agile", er_diagram=diagram)]
)

mcp.run()
```

这是最小的设置。MCP 服务器将你的 ERD 暴露为 AI 代理可以发现和查询的 GraphQL 端点。

## 多应用支持

你可以从一个 MCP 服务器提供多个 ERD：

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

mcp.run()
```

## AppConfig 参数

| 参数 | 类型 | 必需 | 描述 |
|-----------|------|----------|-------------|
| `name` | `str` | 是 | 应用名称，标识 GraphQL 端点 |
| `er_diagram` | `ErDiagram` | 是 | 带有实体定义的 ErDiagram 实例 |
| `description` | `str \| None` | 否 | 给 AI 代理的应用描述 |
| `query_description` | `str \| None` | 否 | Query 类型的描述 |
| `mutation_description` | `str \| None` | 否 | Mutation 类型的描述 |
| `enable_from_attribute_in_type_adapter` | `bool` | 否 | 启用 Pydantic from_attributes 模式（默认：False） |

## 传输模式

`mcp.run()` 方法支持多种传输模式：

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

## 渐进式发现层级

MCP 服务器为 AI 代理实现渐进式发现。不是一次性倾倒完整的 schema，而是分层暴露信息：

```
Layer 0: list_apps          → "有哪些应用可用？"
Layer 1: list_queries       → "此应用支持哪些查询？"
Layer 2: get_query_schema   → "此查询有哪些字段和参数？"
Layer 3: graphql_query      → "执行此 GraphQL 查询"
```

这允许 AI 代理逐步探索 API 而不会被压倒：

1. 代理调用 `list_apps` → 发现 `["blog", "shop"]`
2. 代理为 `blog` 调用 `list_queries` → 发现 `["users", "posts", "createPost"]`
3. 代理为 `users` 调用 `get_query_schema` → 查看可用字段和参数
4. 代理调用 `graphql_query` → 执行 `{ users { id name posts { title } } }`

## 完整示例

```python
from pydantic import BaseModel
from pydantic_resolve import (
    AppConfig,
    Relationship,
    base_entity,
    build_list,
    build_object,
    create_mcp_server,
)


# --- 实体 ---
BaseEntity = base_entity()


class UserEntity(BaseModel, BaseEntity):
    id: int
    name: str


class PostEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='author_id', target=UserEntity, name='author', loader=user_loader)
    ]
    id: int
    title: str
    author_id: int


class BlogEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='id', target=list[PostEntity], name='posts', loader=post_loader)
    ]
    id: int
    name: str


# --- 配置 ---
diagram = BaseEntity.get_diagram()


# --- MCP 服务器 ---
mcp = create_mcp_server(
    apps=[
        AppConfig(
            name="blog",
            er_diagram=diagram,
            description="带有用户和文章的博客系统",
        ),
    ],
    name="Blog API",
)

mcp.run(transport="streamable-http", port=8080)
```

`create_mcp_server()` 会在内部创建隔离的 GraphQL handler，因此这套配置本身不需要 `config_global_resolver(diagram)`，除非你还打算在别处直接调用 `Resolver()`。

## 下一步

- [API 参考](./api_mcp.zh.md) 了解详细的 MCP API 签名
- [GraphQL 指南](./graphql_guide.zh.md) 了解更多 GraphQL 设置
