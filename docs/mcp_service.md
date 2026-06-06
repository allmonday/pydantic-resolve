# MCP Service

[中文版](./mcp_service.zh.md)

MCP (Model Context Protocol) support lets AI agents discover and interact with your GraphQL APIs through progressive disclosure. It builds on the same ERD used by `AutoLoad` and `GraphQLHandler`.

## Install

```bash
pip install pydantic-resolve[mcp]
```

## Goal

You have an ERD with entities and relationships. You want to expose it as an MCP service so AI agents can discover and query your data — without writing any GraphQL schema or resolvers:

```
Agent: "List all blog posts by Alice"
  → MCP server translates to GraphQL query
  → ERD resolves relationships
  → Agent receives the result
```

## Step 1: Create the MCP Server

```python
from pydantic_resolve import AppConfig, create_mcp_server

mcp = create_mcp_server(
    apps=[
        AppConfig(name="blog", er_diagram=diagram),  # (1)
    ]
)

mcp.run()  # (2)
```

1.  `AppConfig` binds your ERD to a named endpoint. `name` identifies the app for AI agents.
2.  Default transport is `stdio` (for Claude Desktop). Use `transport="streamable-http"` for web-based agents.

## Step 2: Serve Multiple Apps

One MCP server can expose multiple ERDs:

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

mcp.run(transport="streamable-http", port=8080)
```

## Progressive Disclosure

The MCP server exposes information in layers, so AI agents can explore incrementally:

```
Layer 0: list_apps          → "What applications are available?"
Layer 1: list_queries       → "What queries does this app support?"
Layer 2: get_query_schema   → "What fields and arguments does this query have?"
Layer 3: graphql_query      → "Execute this GraphQL query"
```

Example flow:

1. Agent calls `list_apps` → discovers `["blog", "shop"]`
2. Agent calls `list_queries` for `blog` → discovers `["users", "posts", "createPost"]`
3. Agent calls `get_query_schema` for `users` → sees available fields and arguments
4. Agent calls `graphql_query` → executes `{ users { id name posts { title } } }`

## Transport Modes

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

## AppConfig Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `str` | Yes | Application name, identifies the GraphQL endpoint |
| `er_diagram` | `ErDiagram` | Yes | ErDiagram instance with entity definitions |
| `description` | `str \| None` | No | Application description for AI agents |
| `query_description` | `str \| None` | No | Description for the Query type |
| `mutation_description` | `str \| None` | No | Description for the Mutation type |
| `enable_from_attribute_in_type_adapter` | `bool` | No | Enable Pydantic from_attributes mode (default: False) |

!!! note
    `create_mcp_server()` builds isolated GraphQL handlers internally, so this setup does not require `config_global_resolver(diagram)` unless you also plan to call `Resolver()` directly elsewhere.

## Next

- [API Reference](./api_mcp.md) for detailed MCP API signatures
- [GraphQL Guide](./graphql_guide.md) for more on GraphQL setup
