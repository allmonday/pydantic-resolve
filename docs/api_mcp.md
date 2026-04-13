# MCP API

[中文版](./api_mcp.zh.md)

## create_mcp_server

```python
from pydantic_resolve import create_mcp_server

mcp = create_mcp_server(
    apps: list[AppConfig],
    name: str = "Pydantic-Resolve GraphQL API",
) -> "FastMCP"
```

Creates an MCP server that exposes multiple ErDiagram applications.

| Parameter | Type | Description |
|-----------|------|-------------|
| `apps` | `list[AppConfig]` | Application configurations |
| `name` | `str` | MCP server name (default: `"Pydantic-Resolve GraphQL API"`) |

Returns a configured `FastMCP` server instance.

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

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Application name (required) |
| `er_diagram` | `ErDiagram` | ErDiagram instance (required) |
| `description` | `str \| None` | Application description for AI agents |
| `query_description` | `str \| None` | Description for the Query type |
| `mutation_description` | `str \| None` | Description for the Mutation type |
| `enable_from_attribute_in_type_adapter` | `bool` | Enable Pydantic from_attributes mode |
| `context_extractor` | `Callable \| None` | Callback to extract request-scoped context from HTTP request |

### context_extractor

Optional callback that extracts request-scoped context (e.g. user identity from Authorization header) from the MCP HTTP request and passes it to `handler.execute(context=...)`, which injects it into `@query`/`@mutation` methods' `_context` parameter.

Signature: `(Context) -> dict | Awaitable[dict]`, supports both sync and async.

```python
from fastmcp.server.context import Context
from fastmcp.server.dependencies import get_http_headers

def extract_user_context(ctx: Context) -> dict:
    # NOTE: get_http_headers() strips 'authorization' by default.
    # You must pass include={"authorization"} to receive it.
    headers = get_http_headers(include={"authorization"})
    auth = headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        # In production, decode JWT here
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

Data flow:

```
HTTP Request (Authorization: Bearer <token>)
  → FastMCP Context
    → context_extractor(ctx) → {"user_id": 1}
      → handler.execute(query, context={"user_id": 1})
        → @query method's _context parameter
```

**Important notes:**

- `get_http_headers()` excludes `authorization`, `content-type`, and other sensitive headers by default. You must pass `include={"authorization"}` to receive the Authorization header.
- When MCP runs via stdio transport (no HTTP request), `get_http_headers()` returns an empty dict.
- Without `context_extractor`, behavior is unchanged (no context is passed).

## MultiAppManager

Internal manager for handling multiple app configurations. Used by `create_mcp_server` internally.

## Progressive Disclosure Tools

The MCP server registers these tools automatically:

| Tool | Layer | Description |
|------|-------|-------------|
| `list_apps` | 0 | Discover available applications |
| `list_queries` | 1 | List queries for an app |
| `list_mutations` | 1 | List mutations for an app |
| `get_query_schema` | 2 | Get detailed query schema |
| `get_mutation_schema` | 2 | Get detailed mutation schema |
| `graphql_query` | 3 | Execute a GraphQL query |
| `graphql_mutation` | 3 | Execute a GraphQL mutation |
