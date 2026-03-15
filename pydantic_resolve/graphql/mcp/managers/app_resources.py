"""App resources container for MCP server."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Set

if TYPE_CHECKING:
    from pydantic_resolve.graphql.handler import GraphQLHandler
    from pydantic_resolve.graphql.mcp.builders.type_tracer import TypeTracer
    from pydantic_resolve.graphql.schema.generators.sdl_generator import SDLGenerator


@dataclass
class AppResources:
    """Container for all resources needed to serve a GraphQL application via MCP.

    This dataclass holds references to the core components needed for MCP:
    - GraphQLHandler: Executes GraphQL queries and mutations
    - TypeTracer: Provides progressive disclosure of type information
    - SDLGenerator: Generates GraphQL Schema Definition Language

    Attributes:
        name: Application name
        description: Application description
        handler: GraphQLHandler instance for executing operations
        tracer: TypeTracer instance for progressive disclosure
        sdl_generator: SDLGenerator instance for schema generation
    """
    name: str
    description: str
    handler: "GraphQLHandler"
    tracer: "TypeTracer"
    sdl_generator: "SDLGenerator"

    @property
    def entity_names(self) -> Set[str]:
        """Get set of entity class names from the ER diagram.

        Returns:
            Set of entity class names
        """
        return {cfg.kls.__name__ for cfg in self.handler.er_diagram.configs}

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
