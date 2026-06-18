"""GraphQL compose UseCase MCP server for Sprint/Task/User management.

Demonstrates the GraphQL-string MCP style:
- describe_compose_schema → compose_query

Independent from ``mcp_server.py`` (the classic progressive-disclosure
server). Both demos use the same ``services.py`` so the underlying
UseCaseService classes stay consistent.
"""

from pydantic_resolve.use_case import (
    UseCaseAppConfig,
    create_use_case_graphql_mcp_server,
)

from demo.use_case.database import init_db
from demo.use_case.services import SprintService, TaskService, UserService


def create_server():
    """Create the GraphQL compose UseCase MCP server."""
    return create_use_case_graphql_mcp_server(
        apps=[
            UseCaseAppConfig(
                name="sprint",
                description="Sprint management with tasks and users",
                services=[UserService, TaskService, SprintService],
            ),
        ],
        name="Sprint UseCase GraphQL MCP Demo",
    )


def main() -> None:
    """Run the MCP server over streamable HTTP."""
    import asyncio

    import uvicorn

    asyncio.run(init_db())
    mcp = create_server()

    mcp_app = mcp.http_app(transport="streamable-http", stateless_http=True)
    uvicorn.run(mcp_app, host="0.0.0.0", port=8007)


if __name__ == "__main__":
    main()
