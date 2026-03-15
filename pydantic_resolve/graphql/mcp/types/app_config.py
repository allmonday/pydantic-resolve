"""App configuration for MCP server."""

from typing import TypedDict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_resolve.utils.er_diagram import ErDiagram


class AppConfig(TypedDict, total=False):
    """Configuration for a GraphQL application in MCP server.

    Attributes:
        name: Application name (required)
        er_diagram: ErDiagram instance containing entity definitions (required)
        description: Optional application description
        query_description: Optional description for Query type
        mutation_description: Optional description for Mutation type
    """
    name: str
    er_diagram: "ErDiagram"
    description: Optional[str]
    query_description: Optional[str]
    mutation_description: Optional[str]
