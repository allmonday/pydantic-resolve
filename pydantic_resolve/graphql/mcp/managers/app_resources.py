"""App resources container for MCP server."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Set

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
    def entity_names(self) -> Set[str]:
        """Get set of entity class names from the ER diagram.

        Returns:
            Set of entity class names
        """
        return {cfg.kls.__name__ for cfg in self.handler.er_diagram.entities}

    @property
    def query_names(self) -> Set[str]:
        """Get set of query names.

        Returns:
            Set of query operation names
        """
        return set(self.handler.query_map.keys())

    @property
    def mutation_names(self) -> Set[str]:
        """Get set of mutation names.

        Returns:
            Set of mutation operation names
        """
        return set(self.handler.mutation_map.keys())
