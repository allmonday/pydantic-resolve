"""
Abstract base class for schema generators.

This module defines the interface that all schema generators must implement,
ensuring consistency between SDL and Introspection output formats.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

from ..type_registry import TypeRegistry, TypeInfo, FieldInfo
from ..type_collector import TypeCollector
from ..type_mapper import TypeMapper

if TYPE_CHECKING:
    from pydantic_resolve.utils.er_diagram import ErDiagram


class SchemaGenerator(ABC):
    """
    Abstract base class for GraphQL schema generators.

    Provides common functionality for type collection and mapping,
    while allowing subclasses to implement specific output formats.
    """

    def __init__(
        self,
        er_diagram: 'ErDiagram',
        validate_conflicts: bool = True
    ):
        """
        Initialize the schema generator.

        Args:
            er_diagram: Entity relationship diagram
            validate_conflicts: Whether to validate field name conflicts
        """
        self.er_diagram = er_diagram
        self.validate_conflicts = validate_conflicts

        # Shared components
        self.registry = TypeRegistry()
        self.collector = TypeCollector(er_diagram, self.registry)
        self.mapper = TypeMapper()

        # Query and mutation maps (set by subclasses if needed)
        self.query_map: Dict[str, Tuple[type, Callable]] = {}
        self.mutation_map: Dict[str, Tuple[type, Callable]] = {}

    @abstractmethod
    def generate(self) -> Any:
        """
        Generate the schema output.

        Returns:
            Schema output (SDL string or introspection dict)
        """
        pass

    @abstractmethod
    def format_type(self, type_info: TypeInfo) -> Any:
        """
        Format a single type definition.

        Args:
            type_info: Type information

        Returns:
            Formatted type definition (string or dict)
        """
        pass

    @abstractmethod
    def format_field(self, field_info: FieldInfo) -> Any:
        """
        Format a single field definition.

        Args:
            field_info: Field information

        Returns:
            Formatted field definition (string or dict)
        """
        pass

    def collect_types(self) -> None:
        """
        Collect all types from the ErDiagram into the registry.
        """
        # Collect entity types
        self.collector.collect_all()

        # Collect input types from query/mutation maps
        if self.query_map or self.mutation_map:
            input_types = self.collector.collect_input_types(
                self.query_map,
                self.mutation_map
            )
            for input_type in input_types:
                type_info = self._build_input_type_info(input_type)
                self.registry.register(type_info)

    def _build_input_type_info(self, kls: type) -> TypeInfo:
        """
        Build TypeInfo for an input type.

        Args:
            kls: Pydantic BaseModel class

        Returns:
            TypeInfo for the input type
        """
        from typing import get_type_hints

        fields: Dict[str, FieldInfo] = {}
        description = self._get_class_description(kls)

        try:
            type_hints = get_type_hints(kls)
        except Exception:
            type_hints = {}

        for field_name, field_type in type_hints.items():
            if field_name.startswith('__'):
                continue

            field_desc = self._get_field_description(kls, field_name)
            fields[field_name] = self.mapper.extract_field_info(
                field_name,
                field_type,
                description=field_desc
            )

        return TypeInfo(
            name=kls.__name__,
            kind="INPUT_OBJECT",
            python_class=kls,
            fields=fields,
            description=description,
            is_input=True
        )

    def _get_class_description(self, kls: type) -> Optional[str]:
        """Get description from class docstring."""
        doc = getattr(kls, '__doc__', None)
        if doc:
            doc = doc.strip()
            if doc:
                return doc
        return None

    def _get_field_description(self, kls: type, field_name: str) -> Optional[str]:
        """Get description from Pydantic field."""
        if not hasattr(kls, 'model_fields'):
            return None

        if field_name not in kls.model_fields:
            return None

        field = kls.model_fields[field_name]
        return getattr(field, 'description', None)

    def get_all_type_names(self) -> List[str]:
        """Get all registered type names."""
        return [t.name for t in self.registry.get_all_types()]
