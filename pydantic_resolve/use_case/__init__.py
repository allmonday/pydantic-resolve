"""UseCase MCP support for pydantic-resolve.

This module provides two independent MCP server factories for exposing
UseCaseService business services to AI agents:

- ``create_use_case_mcp_server`` — classic progressive disclosure style.
  Four tools: ``list_apps`` → ``list_services`` → ``describe_service`` →
  ``call_use_case``. Flat JSON parameters; LLM doesn't need GraphQL
  knowledge.
- ``create_use_case_graphql_mcp_server`` — GraphQL string style with
  4-layer progressive disclosure: ``list_apps`` (cheap discovery) →
  ``describe_compose_schema`` (service + method listing) →
  ``describe_compose_method`` (per-method detail: args / returns /
  SDL with full type tree) → ``compose_query`` (data execution).
  Mirrors the classic server's pattern.

The two servers are intentionally independent: their docstrings and
hints do not cross-reference each other. Pick the one that matches your
LLM's strongest modality (structured JSON vs GraphQL).

Common Components:
- UseCaseService: Base class for defining business services
- UseCaseAppConfig: Configuration for each UseCase application
- FromContext: Marker for server-injected method parameters

Example (classic):
    ```python
    from pydantic_resolve.use_case import (
        create_use_case_mcp_server, UseCaseService, UseCaseAppConfig,
    )

    class UserService(UseCaseService):
        '''User management service.'''

        @classmethod
        async def list_users(cls) -> list[UserDTO]:
            '''Get all users.'''
            ...

    mcp = create_use_case_mcp_server(
        apps=[UseCaseAppConfig(name="user", services=[UserService])],
        name="My API",
    )
    mcp.run()
    ```

Example (graphql):
    ```python
    from pydantic_resolve.use_case import create_use_case_graphql_mcp_server

    mcp = create_use_case_graphql_mcp_server(
        apps=[UseCaseAppConfig(name="user", services=[UserService])],
        name="My GraphQL API",
    )
    mcp.run()
    ```
"""

from pydantic_resolve.use_case.business import UseCaseService
from pydantic_resolve.use_case.context import FromContext
from pydantic_resolve.use_case.server import create_use_case_mcp_server
from pydantic_resolve.use_case.server_graphql import create_use_case_graphql_mcp_server
from pydantic_resolve.use_case.types import UseCaseAppConfig

__all__ = [
    "create_use_case_mcp_server",
    "create_use_case_graphql_mcp_server",
    "UseCaseService",
    "UseCaseAppConfig",
    "FromContext",
]
