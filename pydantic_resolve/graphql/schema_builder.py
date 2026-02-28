"""
GraphQL Schema generator from ERD and @query decorated methods.

This module provides the SchemaBuilder class that generates GraphQL SDL strings.
The implementation delegates to SDLGenerator internally while maintaining
backward compatibility with the public API.
"""

from typing import Dict, List


from .schema.generators.sdl_generator import SDLGenerator
from ..utils.er_diagram import ErDiagram


class SchemaBuilder:
    """
    Generate GraphQL Schema from ERD and @query decorated methods.

    This class maintains backward compatibility while delegating
    to the unified SDLGenerator implementation.
    """

    def __init__(self, er_diagram: ErDiagram, validate_conflicts: bool = True):
        """
        Args:
            er_diagram: Entity relationship diagram
            validate_conflicts: Whether to validate field name conflicts (default True)
        """
        self.er_diagram = er_diagram
        self.validate_conflicts = validate_conflicts

        # Create internal generator
        self._generator = SDLGenerator(er_diagram, validate_conflicts)

    def build_schema(self) -> str:
        """
        Generate complete GraphQL Schema

        Returns:
            GraphQL Schema string
        """
        return self._generator.generate()

    # --- Internal methods preserved for backward compatibility ---
    # These delegate to the generator implementation

    def _build_type_definition(self, entity_cfg) -> str:
        """Generate GraphQL type definition for a single entity."""
        return self._generator._build_type_definition(entity_cfg)

    def _extract_query_methods(self, entity: type) -> List[Dict]:
        """Extract all @query decorated methods from an Entity."""
        return self._generator._extract_query_methods(entity)

    def _extract_mutation_methods(self, entity: type) -> List[Dict]:
        """Extract all @mutation decorated methods from an Entity."""
        return self._generator._extract_mutation_methods(entity)

    def _build_query_def(self, method_info: Dict) -> str:
        """Build single query definition."""
        return self._generator._build_query_def(method_info)

    def _build_mutation_def(self, method_info: Dict) -> str:
        """Build single mutation definition."""
        return self._generator._build_mutation_def(method_info)

    def _map_python_type_to_gql(self, python_type: type) -> str:
        """Map Python type to GraphQL type."""
        return self._generator._map_python_type_to_gql(python_type)

    def _get_entity_by_name(self, name: str):
        """Find entity class by name from ERD."""
        return self._generator._get_entity_by_name(name)

    def _map_return_type_to_gql(self, return_type: type) -> str:
        """Map return type to GraphQL type."""
        return self._generator._map_return_type_to_gql(return_type)

    def _convert_to_query_name(self, method_name: str) -> str:
        """Convert method name to GraphQL query name."""
        return self._generator._convert_to_query_name(method_name)

    def _convert_to_mutation_name(self, method_name: str) -> str:
        """Convert method name to GraphQL mutation name."""
        return self._generator._convert_to_mutation_name(method_name)

    def _validate_all_entities(self) -> None:
        """Validate field name conflicts for all entities."""
        return self._generator._validate_all_entities()

    def _validate_entity_fields(self, entity_cfg) -> None:
        """Validate field conflicts for a single entity."""
        return self._generator._validate_entity_fields(entity_cfg)

    def _collect_nested_pydantic_types(self, processed_types: set) -> set:
        """Recursively collect all nested Pydantic BaseModel types."""
        return self._generator._collect_nested_pydantic_types(processed_types)

    def _build_type_definition_for_class(self, kls: type) -> str:
        """Generate GraphQL type definition for any Pydantic BaseModel class."""
        return self._generator._build_type_definition_for_class(kls)

    def _collect_input_types(self) -> set:
        """Collect all BaseModel types from method parameters as Input Types."""
        return self._generator._collect_input_types()

    def _build_input_definition(self, kls: type) -> str:
        """Generate GraphQL Input type definition for Pydantic BaseModel class."""
        return self._generator._build_input_definition(kls)

    def _map_python_type_to_gql_for_input(self, python_type: type) -> str:
        """Map Python type to GraphQL type (for Input types)."""
        return self._generator._map_python_type_to_gql_for_input(python_type)
