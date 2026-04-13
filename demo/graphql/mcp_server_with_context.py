"""Demo MCP server with context extraction from HTTP headers.

This example demonstrates how to extract request-scoped context
(e.g., user identity from Authorization header) and pass it through
to GraphQL query/mutation methods via the ``_context`` parameter.

It uses entities_v3 which has a ``get_my_posts`` query that filters
posts by the authenticated user's ID from ``_context``.

Usage:
    # Run with streamable-http transport
    uv run python -m demo.graphql.mcp_server_with_context

    # Test with curl:
    # 1. Get the user's own posts (user_id=1, Alice):
    #    curl -X POST http://localhost:8000/mcp/ \
    #      -H "Authorization: Bearer 1" \
    #      -H "Content-Type: application/json" \
    #      -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"graphql_query","arguments":{"query":"{ postEntityV3MyPostsV3 { id title } }","app_name":"blog_v3"}},"id":1}'

    # 2. Get all posts (no context needed):
    #    curl -X POST http://localhost:8000/mcp/ \
    #      -H "Content-Type: application/json" \
    #      -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"graphql_query","arguments":{"query":"{ postEntityV3PostsV3 { id title } }","app_name":"blog_v3"}},"id":2}'

Flow:
    HTTP Request (Authorization: Bearer <user_id>)
      -> FastMCP Context (ctx)
        -> context_extractor(ctx) -> {"user_id": <user_id>}
          -> handler.execute(query, context={"user_id": ...})
            -> get_my_posts(limit, _context={"user_id": ...})
"""

from fastmcp.server.context import Context
from fastmcp.server.dependencies import get_http_headers

from pydantic_resolve.graphql.mcp import create_mcp_server, AppConfig

from demo.graphql.entities_v3 import diagram_v3, init_db_v3


def extract_user_context(ctx: Context) -> dict:
    """Extract user_id from Authorization: Bearer <user_id> header.

    In production, you would decode a JWT token here and extract
    claims like user_id, roles, permissions, etc.

    For this demo, the token IS the user_id (integer).
    """
    # NOTE: get_http_headers() strips 'authorization' by default.
    # Must pass include={"authorization"} to receive it.
    headers = get_http_headers(include={"authorization"})
    auth = headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        try:
            return {"user_id": int(token)}
        except ValueError:
            pass
    return {}


# Define app configuration with context_extractor
apps: list[AppConfig] = [
    AppConfig(
        name="blog_v3",
        er_diagram=diagram_v3,
        description="Blog system with context-aware queries. "
                    "Use Authorization: Bearer <user_id> header to authenticate. "
                    "The myPostsV3 query returns only the authenticated user's posts.",
        enable_from_attribute_in_type_adapter=True,
        context_extractor=extract_user_context,
    ),
]

# Create MCP server
mcp = create_mcp_server(apps=apps, name="Blog GraphQL MCP Server (with Context)")


def main():
    """Run the MCP server."""
    import asyncio
    asyncio.run(init_db_v3())
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
