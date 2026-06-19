"""UseCase MCP support for pydantic-resolve.

This module provides the UseCase GraphQL MCP server factory for
exposing UseCaseService business services to AI agents:

- ``create_use_case_graphql_mcp_server`` — GraphQL string style with
  4-layer progressive disclosure: ``list_apps`` (cheap discovery) →
  ``describe_compose_schema`` (service + method listing) →
  ``describe_compose_method`` (per-method detail: args / returns /
  SDL with full type tree) → ``compose_query`` (data execution).

Common Components:
- UseCaseService: Base class for defining business services
- UseCaseAppConfig: Configuration for each UseCase application
- FromContext: Marker for server-injected method parameters

Example:
    ```python
    from pydantic_resolve.use_case import (
        create_use_case_graphql_mcp_server, UseCaseService, UseCaseAppConfig,
    )

    class UserService(UseCaseService):
        '''User management service.'''

        @classmethod
        async def list_users(cls) -> list[UserDTO]:
            '''Get all users.'''
            ...

    mcp = create_use_case_graphql_mcp_server(
        apps=[UseCaseAppConfig(name="user", services=[UserService])],
        name="My GraphQL API",
    )
    mcp.run()
    ```
"""

from pydantic_resolve.use_case.business import UseCaseService
from pydantic_resolve.use_case.context import FromContext
from pydantic_resolve.use_case.manager import UseCaseAppConfig
from pydantic_resolve.use_case.mcp_server import create_use_case_graphql_mcp_server

__all__ = [
    "create_use_case_graphql_mcp_server",
    "UseCaseService",
    "UseCaseAppConfig",
    "FromContext",
]
