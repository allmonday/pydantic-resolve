"""
Abstract base class for schema generators.

This module defines the interface that all schema generators must implement,
ensuring consistency between SDL and Introspection output formats.
"""

import inspect

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, TYPE_CHECKING

from pydantic import BaseModel

from pydantic_resolve.graphql.schema.type_registry import TypeRegistry, TypeInfo, FieldInfo
from pydantic_resolve.graphql.schema.type_collector import TypeCollector
from pydantic_resolve.graphql.schema.type_mapper import TypeMapper
from pydantic_resolve.utils.er_diagram import Relationship
from pydantic_resolve.utils.class_util import safe_issubclass

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
        self.query_map: dict[str, tuple[type, Callable]] = {}
        self.mutation_map: dict[str, tuple[type, Callable]] = {}

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

        fields: dict[str, FieldInfo] = {}
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

    def get_all_type_names(self) -> list[str]:
        """Get all registered type names."""
        return [t.name for t in self.registry.get_all_types()]

    def _is_relationship_field(self, entity_cfg, field_name: str) -> bool:
        """Check if field is a relationship field."""
        for rel in entity_cfg.relationships:
            if isinstance(rel, Relationship):
                if rel.name == field_name:
                    return True
        return False

    def _get_target_entity_name(self, rel: Relationship) -> Optional[str]:
        """Extract entity class name from a list relationship target."""
        from typing import get_args
        args = get_args(rel.target)
        if args and safe_issubclass(args[0], BaseModel):
            return args[0].__name__
        return None

    def _collect_paginated_relationships(self) -> list[tuple[Relationship, str]]:
        """Collect all one-to-many relationships with page_loader, deduped by target name.

        Returns:
            List of (Relationship, target_entity_name) tuples.
        """
        seen: set[str] = set()
        result: list[tuple[Relationship, str]] = []

        for entity_cfg in self.er_diagram.entities:
            for rel in entity_cfg.relationships:
                if not isinstance(rel, Relationship):
                    continue
                if rel.loader is None:
                    continue
                if not rel.is_list_relationship:
                    continue
                if rel.page_loader is None:
                    continue

                target_name = self._get_target_entity_name(rel)
                if not target_name or target_name in seen:
                    continue
                seen.add(target_name)
                result.append((rel, target_name))

        return result

    def _extract_operation_methods(self, entity: type, operation_type: str) -> list[dict[str, Any]]:
        """Extract all @query or @mutation decorated methods from an entity.

        Args:
            entity: Entity class to scan
            operation_type: "query" or "mutation"

        Returns:
            List of dicts with keys: name, description, params, return_type, entity, method
        """
        import pydantic_resolve.constant as const
        from pydantic_resolve.graphql.utils.naming import to_graphql_field_name

        if operation_type == "query":
            attr = const.GRAPHQL_QUERY_ATTR
            name_attr = const.GRAPHQL_QUERY_NAME_ATTR
            desc_attr = const.GRAPHQL_QUERY_DESCRIPTION_ATTR
        else:
            attr = const.GRAPHQL_MUTATION_ATTR
            name_attr = const.GRAPHQL_MUTATION_NAME_ATTR
            desc_attr = const.GRAPHQL_MUTATION_DESCRIPTION_ATTR

        methods = []

        for name, method in entity.__dict__.items():
            actual_method = method
            if isinstance(method, classmethod):
                actual_method = method.__func__

            if not hasattr(actual_method, attr):
                continue

            try:
                sig = inspect.signature(actual_method)
            except Exception:
                continue

            params = self._extract_method_params(sig)
            return_type = sig.return_annotation

            # Build GraphQL operation name
            base_name = getattr(actual_method, name_attr, None) or name
            graphql_name = to_graphql_field_name(entity.__name__, base_name)
            description = getattr(actual_method, desc_attr, "") or ""

            methods.append({
                'name': graphql_name,
                'description': description,
                'params': params,
                'return_type': return_type,
                'entity': entity,
                'method': actual_method
            })

        return methods

    def _extract_method_params(self, sig: 'inspect.Signature') -> list[dict[str, Any]]:
        """Extract parameter info from a method signature.

        Returns:
            List of dicts with keys: name, type, required, default, definition
        """
        params = []
        for param_name, param in sig.parameters.items():
            if param_name in ('self', 'cls'):
                continue
            if param_name == '_context':
                continue

            param_type = param.annotation
            if param_type == inspect.Parameter.empty:
                continue

            default = param.default
            is_required = default == inspect.Parameter.empty

            params.append({
                'name': param_name,
                'type': param_type,
                'required': is_required,
                'default': default,
            })

        return params
