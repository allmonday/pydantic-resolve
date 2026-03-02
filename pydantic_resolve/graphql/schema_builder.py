"""
GraphQL Schema generator from ERD and @query decorated methods.

This module provides the SchemaBuilder class that generates GraphQL SDL strings.
The implementation delegates to SDLGenerator internally.
"""

from typing import Dict, List

from pydantic_resolve.graphql.schema.generators.sdl_generator import SDLGenerator
from pydantic_resolve.utils.er_diagram import ErDiagram


class SchemaBuilder:
    """
    Generate GraphQL Schema from ERD and @query decorated methods.

    This class delegates to SDLGenerator internally.
    """

    def __init__(self, er_diagram: ErDiagram, validate_conflicts: bool = True):
        """
        Args:
            er_diagram: Entity relationship diagram
            validate_conflicts: Whether to validate field name conflicts (default True)
        """
        self.er_diagram = er_diagram
        self.validate_conflicts = validate_conflicts
        self._generator = SDLGenerator(er_diagram, validate_conflicts)

    def build_schema(self) -> str:
        """
        Generate complete GraphQL Schema

        Returns:
            GraphQL Schema string
        """
        return self._generator.generate()

    def _extract_query_methods(self, entity: type) -> List[Dict]:
        """Extract all @query decorated methods from an Entity."""
        return self._generator._extract_query_methods(entity)

    def _extract_mutation_methods(self, entity: type) -> List[Dict]:
        """Extract all @mutation decorated methods from an Entity."""
        return self._generator._extract_mutation_methods(entity)
