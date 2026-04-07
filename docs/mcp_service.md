# MCP Service

[中文版](./mcp_service.zh.md)

MCP (Model Context Protocol) support lets AI agents discover and interact with your GraphQL APIs through progressive disclosure. It builds on the same ERD used by `AutoLoad` and `GraphQLHandler`.

## Install

```bash
pip install pydantic-resolve[mcp]
```

## Quick Start

```python
from pydantic_resolve import AppConfig, create_mcp_server

# diagram is your configured ErDiagram
mcp = create_mcp_server(
    apps=[AppConfig(name="agile", er_diagram=diagram)]
)

mcp.run()
```

That is the minimum setup. The MCP server exposes your ERD as a GraphQL endpoint that AI agents can discover and query.

## Multi-App Support

You can serve multiple ERDs from one MCP server:

```python
mcp = create_mcp_server(
    apps=[
        AppConfig(
            name="blog",
            er_diagram=blog_diagram,
            description="Blog system with users and posts",
        ),
        AppConfig(
            name="shop",
            er_diagram=shop_diagram,
            description="E-commerce system with products and orders",
        ),
    ],
    name="My API",
)

mcp.run()
```

## AppConfig Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `str` | Yes | Application name, identifies the GraphQL endpoint |
| `er_diagram` | `ErDiagram` | Yes | ErDiagram instance with entity definitions |
| `description` | `str \| None` | No | Application description for AI agents |
| `query_description` | `str \| None` | No | Description for the Query type |
| `mutation_description` | `str \| None` | No | Description for the Mutation type |
| `enable_from_attribute_in_type_adapter` | `bool` | No | Enable Pydantic from_attributes mode (default: False) |

## Transport Modes

The `mcp.run()` method supports multiple transport modes:

```python
# HTTP transport (recommended for web-based agents)
mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)

# SSE (Server-Sent Events) transport
mcp.run(transport="sse", port=8080)

# stdio transport (for Claude Desktop integration)
mcp.run(transport="stdio")
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `transport` | Transport mode: `"stdio"`, `"streamable-http"`, `"sse"` | `"stdio"` |
| `host` | Host address to bind | `"127.0.0.1"` |
| `port` | Port number | `8000` |

## Progressive Disclosure Layers

The MCP server implements progressive disclosure for AI agents. Instead of dumping the full schema at once, it exposes information in layers:

```
Layer 0: list_apps          → "What applications are available?"
Layer 1: list_queries       → "What queries does this app support?"
Layer 2: get_query_schema   → "What fields and arguments does this query have?"
Layer 3: graphql_query      → "Execute this GraphQL query"
```

This allows AI agents to incrementally explore the API without being overwhelmed:

1. Agent calls `list_apps` → discovers `["blog", "shop"]`
2. Agent calls `list_queries` for `blog` → discovers `["users", "posts", "createPost"]`
3. Agent calls `get_query_schema` for `users` → sees available fields and arguments
4. Agent calls `graphql_query` → executes `{ users { id name posts { title } } }`

## Complete Example

```python
from pydantic import BaseModel
from pydantic_resolve import (
    AppConfig,
    Relationship,
    base_entity,
    build_list,
    build_object,
    config_global_resolver,
    create_mcp_server,
)


# --- Entities ---
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


# --- Configure ---
diagram = BaseEntity.get_diagram()
config_global_resolver(diagram)


# --- MCP Server ---
mcp = create_mcp_server(
    apps=[
        AppConfig(
            name="blog",
            er_diagram=diagram,
            description="Blog system with users and posts",
        ),
    ],
    name="Blog API",
)

mcp.run(transport="streamable-http", port=8080)
```

## Next

- [API Reference](./api_mcp.md) for detailed MCP API signatures
- [GraphQL Guide](./graphql_guide.md) for more on GraphQL setup
