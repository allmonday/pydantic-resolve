"""
GraphQL Schema builder from ERD and @query decorated methods.

This module provides the SchemaBuilder class that builds GraphQL SDL strings.
The implementation delegates to SDLBuilder internally.
"""

from pydantic_resolve.graphql.schema.generators.sdl_builder import SDLBuilder
from pydantic_resolve.utils.er_diagram import ErDiagram


class SchemaBuilder:
    """
    Build GraphQL Schema from ERD and @query decorated methods.

    This class delegates to SDLBuilder internally.
    """

    def __init__(self, er_diagram: ErDiagram, validate_conflicts: bool = True):
        """
        Args:
            er_diagram: Entity relationship diagram
            validate_conflicts: Whether to validate field name conflicts (default True)
        """
        self.er_diagram = er_diagram
        self.validate_conflicts = validate_conflicts
        self._builder = SDLBuilder(er_diagram, validate_conflicts)

    def build_schema(self) -> str:
        """
        Build complete GraphQL Schema

        Returns:
            GraphQL Schema string
        """
        return self._builder.generate()

    def _extract_query_methods(self, entity: type) -> list[dict]:
        """Extract all @query decorated methods from an Entity."""
        return self._builder._extract_query_methods(entity)

    def _extract_mutation_methods(self, entity: type) -> list[dict]:
        """Extract all @mutation decorated methods from an Entity."""
        return self._builder._extract_mutation_methods(entity)
