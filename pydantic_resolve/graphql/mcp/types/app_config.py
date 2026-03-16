"""App configuration for MCP server."""

from pydantic import BaseModel

from pydantic_resolve.utils.er_diagram import ErDiagram


class AppConfig(BaseModel):
    """Configuration for a GraphQL application in MCP server.

    Attributes:
        name: Application name (required)
        er_diagram: ErDiagram instance containing entity definitions (required)
        description: Optional application description
        query_description: Optional description for Query type
        mutation_description: Optional description for Mutation type
        enable_from_attribute_in_type_adapter: Enable Pydantic from_attributes mode.
            Allows loaders to return Pydantic instances instead of dictionaries.
            Default is False.
    """

    name: str
    er_diagram: ErDiagram
    description: str | None = None
    query_description: str | None = None
    mutation_description: str | None = None
    enable_from_attribute_in_type_adapter: bool = False
