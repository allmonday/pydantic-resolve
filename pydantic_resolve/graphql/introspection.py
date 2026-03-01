"""
GraphQL introspection support.

Handles __schema, __type, and other introspection queries for GraphiQL compatibility.
This module provides the IntrospectionHelper class that delegates to IntrospectionGenerator.
"""

from typing import Any, Callable, Dict, Tuple

from pydantic_resolve.graphql.schema.generators.introspection_generator import IntrospectionGenerator


class IntrospectionHelper:
    """
    GraphQL introspection helper.

    Provides introspection support for GraphiQL and other GraphQL tools.
    Delegates to IntrospectionGenerator internally.
    """

    def __init__(
        self,
        er_diagram,
        query_map: Dict[str, Tuple[type, Callable]],
        mutation_map: Dict[str, Tuple[type, Callable]]
    ):
        """
        Args:
            er_diagram: Entity relationship diagram
            query_map: Mapping of query names to (entity, method) tuples
            mutation_map: Mapping of mutation names to (entity, method) tuples
        """
        self.er_diagram = er_diagram
        self.query_map = query_map
        self.mutation_map = mutation_map

        # Create internal generator
        self._generator = IntrospectionGenerator(
            er_diagram, query_map, mutation_map
        )

    def is_introspection_query(self, query: str) -> bool:
        """Check if this is an introspection query."""
        return self._generator.is_introspection_query(query)

    async def execute(self, query: str) -> Dict[str, Any]:
        """Execute introspection query - returns full introspection data to support GraphiQL."""
        return await self._generator.execute(query)
