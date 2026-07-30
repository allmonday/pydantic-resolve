"""App resources container for MCP server."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from pydantic_resolve.graphql.handler import GraphQLHandler
    from pydantic_resolve.graphql.mcp.builders.introspection_query_helper import IntrospectionQueryHelper
    from pydantic_resolve.graphql.schema.generators.sdl_builder import SDLBuilder


@dataclass
class AppResources:
    """Container for all resources needed to serve a GraphQL application via MCP.

    This dataclass holds references to the core components needed for MCP:
    - GraphQLHandler: Executes GraphQL queries and mutations
    - IntrospectionQueryHelper: Queries introspection data for progressive disclosure
    - SDLBuilder: Builds GraphQL Schema Definition Language

    Attributes:
        name: Application name
        description: Application description
        handler: GraphQLHandler instance for executing operations
        introspection_helper: IntrospectionQueryHelper instance for progressive disclosure
        sdl_builder: SDLBuilder instance for schema generation
        context_extractor: Optional callback to extract request-scoped context from FastMCP Context
    """
    name: str
    description: str
    handler: "GraphQLHandler"
    introspection_helper: "IntrospectionQueryHelper"
    sdl_builder: "SDLBuilder"
    context_extractor: Callable[[Any], dict | Awaitable[dict]] | None = field(default=None)

    @property
    def entity_names(self) -> set[str]:
        """Get set of entity class names from the ER diagram.

        Returns:
            Set of entity class names
        """
        return {cfg.kls.__name__ for cfg in self.handler.er_diagram.entities}

    @property
    def query_names(self) -> set[str]:
        """All query operations as ``<entity>.<method>`` identifiers.

        Under the grouped layout the map is ``{entity: {method: ...}}``; these
        identifiers stay unique (and ``len()`` accurate) even when two entities
        share a method name.
        """
        return {
            f"{entity}.{method}"
            for entity, group in self.handler.query_map.items()
            for method in group
        }

    @property
    def mutation_names(self) -> set[str]:
        """All mutation operations as ``<entity>.<method>`` identifiers."""
        return {
            f"{entity}.{method}"
            for entity, group in self.handler.mutation_map.items()
            for method in group
        }

    @property
    def query_groups(self) -> set[str]:
        """Entity group names that expose at least one query."""
        return set(self.handler.query_map.keys())

    @property
    def mutation_groups(self) -> set[str]:
        """Entity group names that expose at least one mutation."""
        return set(self.handler.mutation_map.keys())
