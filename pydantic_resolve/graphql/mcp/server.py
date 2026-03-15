"""MCP Server implementation for pydantic-resolve GraphQL.

This module provides the main entry point for creating an MCP server that exposes
pydantic-resolve GraphQL applications with progressive disclosure support.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from pydantic_resolve.graphql.mcp.managers.multi_app_manager import MultiAppManager
from pydantic_resolve.graphql.mcp.tools.multi_app_tools import register_multi_app_tools
from pydantic_resolve.graphql.mcp.types.app_config import AppConfig

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def create_mcp_server(
    apps: List[AppConfig],
    name: str = "Pydantic-Resolve GraphQL API",
) -> "FastMCP":
    """Create an MCP server that exposes multiple ErDiagram as independent GraphQL apps.

    This function creates a FastMCP server with progressive disclosure support,
    allowing AI agents to discover and interact with GraphQL APIs incrementally.

    Progressive Disclosure Layers:
    - Layer 0: list_apps - Discover available applications
    - Layer 1: list_queries, list_mutations - List operations
    - Layer 2: get_query_schema, get_mutation_schema - Get detailed schema
    - Layer 3: graphql_query. graphql_mutation - Execute operations

    Args:
        apps: List of app configurations. Each config must include:
            - name: Application name (required)
            - er_diagram: ErDiagram instance (required)
            - description: Application description (optional)
            - query_description: Query type description (optional)
            - mutation_description: Mutation type description (optional)
        name: MCP server name (default: "Pydantic-Resolve GraphQL API")

    Returns:
        A configured FastMCP server instance ready to run

    Example:
        ```python
        from pydantic_resolve import base_entity, config_global_resolver
        from pydantic_resolve.graphql.mcp import create_mcp_server

        # Define entities
        BaseEntity = base_entity()
        config_global_resolver(BaseEntity.get_diagram())

        # Create MCP server
        apps = [
            {
                "name": "blog",
                "er_diagram": BaseEntity.get_diagram(),
                "description": "Blog system with users and posts",
            }
        ]

        mcp = create_mcp_server(apps=apps, name="Blog API")
        mcp.run()
        ```

    Raises:
        ValueError: If apps list is empty or contains invalid configurations
    """
    from mcp.server.fastmcp import FastMCP

    if not apps:
        raise ValueError("apps list cannot be empty")

    # Validate app configs
    for i, app in enumerate(apps):
        if "name" not in app:
            raise ValueError(f"App config at index {i} missing required field: name")
        if "er_diagram" not in app:
            raise ValueError(f"App config at index {i} missing required field: er_diagram")

    # Create manager with all app resources
    manager = MultiAppManager(apps)

    # Create FastMCP server
    mcp = FastMCP(name)

    # Register all tools
    register_multi_app_tools(mcp, manager)

    return mcp
