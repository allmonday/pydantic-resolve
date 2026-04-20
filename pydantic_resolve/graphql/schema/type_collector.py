"""
Unified type collection logic for GraphQL schema generation.

This module provides a centralized TypeCollector that collects all types
from an ErDiagram, including:
- Entity types from ERD configs
- Nested Pydantic types referenced in fields
- Input types from method parameters
"""

import inspect
from typing import Any, Callable, Optional, get_type_hints

from pydantic import BaseModel

from .type_registry import TypeRegistry
import pydantic_resolve.constant as const
from pydantic_resolve.utils.class_util import safe_issubclass
from pydantic_resolve.utils.types import get_core_types
from pydantic_resolve.utils.er_diagram import ErDiagram


class TypeCollector:
    """
    Collects all GraphQL types from an ErDiagram.

    This is the unified type collection logic used by both
    SDL and Introspection generators.
    """

    def __init__(self, er_diagram: ErDiagram, registry: Optional[TypeRegistry] = None):
        """
        Args:
            er_diagram: Entity relationship diagram containing entity configs
            registry: Optional TypeRegistry to use (creates new one if None)
        """
        self.er_diagram = er_diagram
        self.registry = registry or TypeRegistry()

    def collect_all(self) -> TypeRegistry:
        """
        Collect all types from the ErDiagram.

        Returns:
            TypeRegistry populated with all types
        """
        # 1. Collect entity types from ERD
        entity_types = self._collect_entity_types()

        # 2. Collect nested Pydantic types from entity fields
        self._collect_nested_pydantic_types(entity_types)

        return self.registry

    def collect_all_types(self) -> dict[str, type]:
        """Collect all types from ERD: entities, relationship targets, and nested types.

        Returns:
            Dictionary mapping type names to type classes.
        """
        from pydantic_resolve.utils.er_diagram import Relationship

        collected: dict[str, type] = {}

        # 1. Collect entity types from ERD
        for entity_cfg in self.er_diagram.entities:
            collected[entity_cfg.kls.__name__] = entity_cfg.kls

        # 2. Collect types from Relationship.target
        for entity_cfg in self.er_diagram.entities:
            for rel in entity_cfg.relationships:
                if isinstance(rel, Relationship):
                    for target_class in get_core_types(rel.target):
                        if safe_issubclass(target_class, BaseModel):
                            if target_class.__name__ not in collected:
                                collected[target_class.__name__] = target_class

        # 3. Collect nested Pydantic types from all collected types' fields
        nested = self.collect_nested_pydantic_types(list(collected.values()))
        for name, cls in nested.items():
            if name not in collected:
                collected[name] = cls

        return collected

    def collect_input_types(
        self,
        query_map: Optional[dict[str, tuple[type, Callable]]] = None,
        mutation_map: Optional[dict[str, tuple[type, Callable]]] = None
    ) -> set[type]:
        """
        Collect all BaseModel types from method parameters as Input Types.

        Args:
            query_map: Optional mapping of query names to (entity, method) tuples
            mutation_map: Optional mapping of mutation names to (entity, method) tuples

        Returns:
            Set of all BaseModel types that need input definitions
        """
        input_types: set[type] = set()
        visited: set[str] = set()

        def collect_from_type(param_type: Any) -> None:
            """Recursively collect BaseModel types."""
            core_types = get_core_types(param_type)

            for core_type in core_types:
                if safe_issubclass(core_type, BaseModel):
                    type_name = core_type.__name__
                    if type_name not in visited:
                        visited.add(type_name)
                        input_types.add(core_type)

                        # Recursively collect nested BaseModel types
                        try:
                            type_hints = get_type_hints(core_type)
                            for field_type in type_hints.values():
                                collect_from_type(field_type)
                        except Exception:
                            pass

        # Collect from query methods in ERD entities
        for entity_cfg in self.er_diagram.entities:
            methods = self._extract_query_mutation_methods(entity_cfg.kls)
            for method in methods:
                try:
                    sig = inspect.signature(method)
                    for param_name, param in sig.parameters.items():
                        if param_name in ('self', 'cls'):
                            continue
                        if param.annotation != inspect.Parameter.empty:
                            collect_from_type(param.annotation)
                except Exception:
                    pass

        # Also collect from provided query/mutation maps
        if query_map:
            for _, (_, method) in query_map.items():
                self._collect_from_method(method, collect_from_type)

        if mutation_map:
            for _, (_, method) in mutation_map.items():
                self._collect_from_method(method, collect_from_type)

        return input_types

    def _collect_from_method(self, method: Callable, collector: Callable[[Any], None]) -> None:
        """Collect types from method parameters."""
        try:
            sig = inspect.signature(method)
            for param_name, param in sig.parameters.items():
                if param_name in ('self', 'cls'):
                    continue
                if param.annotation != inspect.Parameter.empty:
                    collector(param.annotation)
        except Exception:
            pass

    def _collect_entity_types(self) -> list[type]:
        """Collect all entity types from ERD configs."""
        entity_types = []
        for entity_cfg in self.er_diagram.entities:
            entity_types.append(entity_cfg.kls)
        return entity_types

    def collect_nested_pydantic_types(
        self,
        entities: list[type],
        visited: Optional[set[str]] = None
    ) -> dict[str, type]:
        """
        Recursively collect all Pydantic BaseModel types referenced in entity fields.

        Args:
            entities: List of entity classes to scan
            visited: Set of already visited type names

        Returns:
            Dictionary mapping type names to type classes
        """
        if visited is None:
            visited = set()

        collected: dict[str, type] = {}

        for entity in entities:
            type_name = entity.__name__
            if type_name in visited:
                continue
            visited.add(type_name)

            # Scan all fields of the entity
            try:
                type_hints = get_type_hints(entity)
            except Exception:
                type_hints = getattr(entity, '__annotations__', {})

            for field_name, field_type in type_hints.items():
                if field_name.startswith('__'):
                    continue

                core_types = get_core_types(field_type)
                for core_type in core_types:
                    if safe_issubclass(core_type, BaseModel):
                        if core_type.__name__ not in collected and core_type.__name__ not in visited:
                            collected[core_type.__name__] = core_type

        # Recursively collect nested types of newly discovered types
        if collected:
            nested_types = self.collect_nested_pydantic_types(
                list(collected.values()), visited
            )
            collected.update(nested_types)

        return collected

    # Alias for backward compatibility
    _collect_nested_pydantic_types = collect_nested_pydantic_types

    def collect_enum_types(self, types_to_scan: list[type]) -> list[type]:
        """Collect all enum types from a list of classes.

        Scans type hints of each class for enum types.

        Args:
            types_to_scan: List of classes to scan for enum usage

        Returns:
            Deduplicated list of enum types
        """
        from pydantic_resolve.graphql.type_mapping import is_enum_type

        enums: list[type] = []
        visited: set[str] = set()

        for kls in types_to_scan:
            try:
                type_hints = get_type_hints(kls)
            except Exception:
                continue

            for field_type in type_hints.values():
                core_types_list = get_core_types(field_type)
                for ct in core_types_list:
                    if is_enum_type(ct):
                        type_name = ct.__name__
                        if type_name not in visited:
                            visited.add(type_name)
                            enums.append(ct)

        return enums

    def _extract_query_mutation_methods(self, entity: type) -> list[Callable]:
        """
        Extract all @query and @mutation decorated methods from an Entity.

        Args:
            entity: Entity class to scan

        Returns:
            List of method objects
        """
        methods = []

        for name, method in entity.__dict__.items():
            # Handle classmethod - access underlying function
            actual_method = method
            if isinstance(method, classmethod):
                actual_method = method.__func__

            # Check if it has @query or @mutation decorator marker
            if (hasattr(actual_method, const.GRAPHQL_QUERY_ATTR) or
                hasattr(actual_method, const.GRAPHQL_MUTATION_ATTR)):
                methods.append(actual_method)

        return methods
