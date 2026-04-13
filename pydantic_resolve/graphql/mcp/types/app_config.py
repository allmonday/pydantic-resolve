"""App configuration for MCP server."""

from typing import Any, Awaitable, Callable

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
        context_extractor: Optional callback that extracts request-scoped context
            (e.g. user identity from Authorization header). Receives the FastMCP
            Context object and returns a dict passed as ``context=`` to
            ``handler.execute()``. Can be sync or async.
    """

    model_config = {"arbitrary_types_allowed": True}

    name: str
    er_diagram: ErDiagram
    description: str | None = None
    query_description: str | None = None
    mutation_description: str | None = None
    enable_from_attribute_in_type_adapter: bool = False
    context_extractor: Callable[[Any], dict | Awaitable[dict]] | None = None
