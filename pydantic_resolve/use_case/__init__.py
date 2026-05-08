"""UseCase MCP support for pydantic-resolve.

This module provides MCP server implementation for exposing UseCaseService
business services to AI agents with progressive disclosure support.

Main Components:
- create_use_case_mcp_server: Create an MCP server for multiple UseCase apps
- UseCaseService: Base class for defining business services
- UseCaseAppConfig: Configuration for each UseCase application

Progressive Disclosure Layers:
- Layer 0: list_apps - Discover available applications
- Layer 1: list_services - List services in an app
- Layer 2: describe_service - Get method signatures and DTO types
- Layer 3: call_use_case - Execute a method

Example:
    ```python
    from pydantic_resolve.use_case import create_use_case_mcp_server, UseCaseService, UseCaseAppConfig

    class UserService(UseCaseService):
        '''User management service.'''

        @classmethod
        async def list_users(cls) -> list[UserDTO]:
            '''Get all users.'''
            ...

    mcp = create_use_case_mcp_server(
        apps=[
            UseCaseAppConfig(name="user", services=[UserService]),
        ],
        name="My API",
    )
    mcp.run()
    ```
"""

from pydantic_resolve.use_case.business import UseCaseService
from pydantic_resolve.use_case.context import FromContext
from pydantic_resolve.use_case.server import create_use_case_mcp_server
from pydantic_resolve.use_case.types import UseCaseAppConfig

__all__ = ["create_use_case_mcp_server", "UseCaseService", "UseCaseAppConfig", "FromContext"]
