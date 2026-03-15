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

from pydantic_resolve import config_global_resolver
from pydantic_resolve.graphql.mcp import create_mcp_server

from demo.graphql.entities import BaseEntity

# Configure global resolver with ER diagram
config_global_resolver(BaseEntity.get_diagram())

# Define app configuration
apps = [
    {
        "name": "blog",
        "er_diagram": BaseEntity.get_diagram(),
        "description": "Blog system with users, posts, and comments. "
                      "Supports CRUD operations for all entities with relationship loading.",
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
