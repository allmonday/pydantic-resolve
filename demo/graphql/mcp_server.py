"""Demo MCP server using entities from demo/graphql/entities.py.

This example demonstrates how to create an MCP server that exposes
pydantic-resolve GraphQL applications with progressive disclosure support.

Usage:
    # Run with stdio transport (default)
    uv run python -m demo.graphql.mcp_server

    # Or import and use in your own code
    from demo.graphql.mcp_server import mcp
    mcp.run(transport="streamable-http")
"""

from pydantic_resolve.graphql.mcp import create_mcp_server, AppConfig

from demo.graphql.entities import BaseEntity
from demo.graphql.entities_v2 import diagram_v2

diagram = BaseEntity.get_diagram()

# Define app configuration
apps: list[AppConfig] = [
    {
        "name": "blog_v1",
        "er_diagram": diagram,
        "description": "Blog system with users, posts, and comments. "
                      "Supports CRUD operations for all entities with relationship loading.",
        "enable_from_attribute_in_type_adapter": True,  # Enable from_attributes mode for type adapter validation
    },
    {
        "name": "blog_v2",
        "er_diagram": diagram_v2,
        "description": "Blog system with users, posts, and comments. "
                      "Supports CRUD operations for all entities with relationship loading. schema is different from blog_v1.",
        "enable_from_attribute_in_type_adapter": True,  # Enable from_attributes mode for type adapter validation
    }
]

# Create MCP server
mcp = create_mcp_server(apps=apps, name="Blog GraphQL MCP Server")


def main():
    """Run the MCP server."""
    # Run with stdio transport (default for Claude Desktop)
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
