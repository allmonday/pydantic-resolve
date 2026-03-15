"""MCP (Model Context Protocol) support for pydantic-resolve GraphQL.

This module provides MCP server implementation for exposing pydantic-resolve
GraphQL applications to AI agents with progressive disclosure support.

Main Components:
- create_mcp_server: Create an MCP server for multiple ErDiagram apps
- MultiAppManager: Manager for handling multiple GraphQL applications
- TypeTracer: Progressive disclosure support for GraphQL types
- MCP Tools: 7 tools for progressive disclosure

Progressive Disclosure Layers:
- Layer 0: list_apps - Discover available applications
- Layer 1: list_queries, list_mutations - List operations
- Layer 2: get_query_schema, get_mutation_schema - Get detailed schema
- Layer 3: graphql_query, graphql_mutation - Execute operations

Example:
    ```python
    from pydantic_resolve import base_entity, config_global_resolver
    from pydantic_resolve.graphql.mcp import create_mcp_server

    # Define entities
    BaseEntity = base_entity()
    config_global_resolver(BaseEntity.get_diagram())

    # Create MCP server
    apps = [{
        "name": "my_api",
        "er_diagram": BaseEntity.get_diagram(),
        "description": "My API description",
    }]

    mcp = create_mcp_server(apps=apps)
    mcp.run()
    ```
"""

from pydantic_resolve.graphql.mcp.server import create_mcp_server
from pydantic_resolve.graphql.mcp.types.app_config import AppConfig
from pydantic_resolve.graphql.mcp.types.errors import MCPErrors

__all__ = ["create_mcp_server", "AppConfig", "MCPErrors"]
