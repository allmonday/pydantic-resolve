"""
GraphQL introspection support.

Handles __schema, __type, and other introspection queries for GraphiQL compatibility.
This module provides the IntrospectionHelper class that delegates to IntrospectionGenerator.
"""

from typing import Any, Callable, Dict, Optional, Tuple

from .schema.generators.introspection_generator import IntrospectionGenerator


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

    def parse_introspection_query(self, query: str) -> Dict[str, Any]:
        """Parse introspection query and extract requested fields."""
        return self._generator._parse_introspection_query(query)

    async def execute(self, query: str) -> Dict[str, Any]:
        """Execute introspection query - returns full introspection data to support GraphiQL."""
        return await self._generator.execute(query)

    # --- Internal methods preserved for backward compatibility ---

    def _extract_type_name_from_query(self, query: str) -> Optional[str]:
        """Extract type name from query."""
        return self._generator._extract_type_name_from_query(query)

    def _get_introspection_type(self, type_name: str) -> Optional[Dict[str, Any]]:
        """Get introspection info for a specific type."""
        return self._generator._get_introspection_type(type_name)

    def _get_introspection_types(self) -> list:
        """Get introspection type list."""
        return self._generator._get_all_introspection_types()

    def _get_introspection_query_fields(self) -> list:
        """Get introspection fields for Query type."""
        return self._generator._get_query_fields()

    def _get_introspection_mutation_fields(self) -> list:
        """Get introspection fields for Mutation type."""
        return self._generator._get_mutation_fields()

    def _get_introspection_fields(self, entity: type) -> list:
        """Get introspection fields for entity."""
        return self._generator._get_entity_fields(entity)

    def _get_introspection_input_fields(self, input_type: type) -> list:
        """Get introspection fields for an Input Type."""
        return self._generator._get_input_fields(input_type)

    def _collect_input_types_for_introspection(self) -> set:
        """Collect all BaseModel types from method parameters as Input Types."""
        return self._generator._collect_input_types_from_maps()

    def _collect_nested_pydantic_types(self, entities: list, visited: Optional[set] = None) -> Dict[str, type]:
        """Recursively collect all Pydantic BaseModel types."""
        return self._generator._collect_nested_pydantic_types(entities, visited)

    def _build_graphql_type(self, field_type: Any) -> Dict[str, Any]:
        """Map Python type to GraphQL type definition."""
        return self._generator._build_graphql_type(field_type)

    def _build_input_graphql_type(self, field_type: Any) -> Dict[str, Any]:
        """Map Python type to GraphQL Input type definition."""
        return self._generator._build_input_graphql_type(field_type)

    def _get_field_description(self, entity: type, field_name: str) -> Optional[str]:
        """Get field description information."""
        return self._generator._get_field_description(entity, field_name)

    def _get_class_description(self, entity: type) -> str:
        """Get class description information."""
        return self._generator._get_class_description(entity)
