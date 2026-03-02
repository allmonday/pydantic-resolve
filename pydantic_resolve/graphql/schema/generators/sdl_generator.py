"""
SDL (Schema Definition Language) generator.

This module generates GraphQL SDL strings from ErDiagram,
using the unified type collection and mapping logic.
"""

import inspect
from typing import Dict, List, Set, get_args, get_origin, get_type_hints

from pydantic import BaseModel

from pydantic_resolve.graphql.schema.generators.base import SchemaGenerator
from pydantic_resolve.graphql.schema.type_registry import TypeInfo, FieldInfo
from pydantic_resolve.utils.class_util import safe_issubclass
from pydantic_resolve.utils.er_diagram import Relationship
from pydantic_resolve.utils.types import get_core_types
from pydantic_resolve.graphql.type_mapping import map_scalar_type, is_enum_type, get_enum_names
from pydantic_resolve.graphql.exceptions import FieldNameConflictError


class SDLGenerator(SchemaGenerator):
    """
    Generates GraphQL SDL (Schema Definition Language) strings.

    This is the refactored implementation that uses the unified
    type collection and mapping logic.
    """

    def generate(self) -> str:
        """
        Generate complete GraphQL Schema.

        Returns:
            GraphQL Schema string
        """
        # Runtime field conflict validation
        if self.validate_conflicts:
            self._validate_all_entities()

        enum_defs: List[str] = []
        input_defs: List[str] = []
        type_defs: List[str] = []
        query_defs: List[str] = []
        mutation_defs: List[str] = []
        processed_types = set()
        processed_input_types = set()
        processed_enums = set()

        # Generate all entity types
        for entity_cfg in self.er_diagram.configs:
            type_def = self._build_type_definition(entity_cfg)
            type_defs.append(type_def)
            processed_types.add(entity_cfg.kls)

            # Collect enum types from entity
            self._add_enum_definitions(entity_cfg.kls, enum_defs, processed_enums)

            # Extract @query methods
            query_methods = self._extract_query_methods(entity_cfg.kls)
            for method in query_methods:
                query_defs.append(self._build_query_def(method))

            # Extract @mutation methods
            mutation_methods = self._extract_mutation_methods(entity_cfg.kls)
            for method in mutation_methods:
                mutation_defs.append(self._build_mutation_def(method))

        # Collect and generate nested Pydantic types
        nested_types = self._collect_nested_pydantic_types(processed_types)
        for nested_type in nested_types:
            if nested_type not in processed_types:
                type_def = self._build_type_definition_for_class(nested_type)
                type_defs.append(type_def)
                processed_types.add(nested_type)

                # Collect enum types from nested types
                self._add_enum_definitions(nested_type, enum_defs, processed_enums)

        # Collect and generate Input Types
        input_types = self._collect_input_types()
        for input_type in input_types:
            if input_type not in processed_input_types:
                input_def = self._build_input_definition(input_type)
                input_defs.append(input_def)
                processed_input_types.add(input_type)

                # Collect enum types from input types
                self._add_enum_definitions(input_type, enum_defs, processed_enums)

        # Assemble schema
        schema_parts = []

        # Add enum definitions first (before types)
        if enum_defs:
            schema_parts.append("\n".join(enum_defs))

        if input_defs:
            schema_parts.append("\n".join(input_defs))

        if type_defs:
            schema_parts.append("\n".join(type_defs))

        schema = "\n\n".join(schema_parts) + "\n\n"

        # Query type
        schema += "type Query {\n"
        if query_defs:
            schema += "\n".join(f"  {qd}" for qd in query_defs) + "\n"
        schema += "}\n\n"

        # Mutation type
        if mutation_defs:
            schema += "type Mutation {\n"
            schema += "\n".join(f"  {md}" for md in mutation_defs) + "\n"
            schema += "}\n"

        return schema

    def format_type(self, type_info: TypeInfo) -> str:
        """Format a type definition as SDL string."""
        fields = []
        for field_info in type_info.fields.values():
            fields.append(self.format_field(field_info))

        keyword = "input" if type_info.is_input else "type"
        return f"{keyword} {type_info.name} {{\n" + "\n".join(fields) + "\n}"

    def format_field(self, field_info: FieldInfo) -> str:
        """Format a field definition as SDL string."""
        gql_type = field_info.graphql_type_name

        if field_info.is_list:
            gql_type = f"[{gql_type}!]!"

        if not field_info.is_optional and not field_info.is_list:
            gql_type = f"{gql_type}!"

        return f"  {field_info.name}: {gql_type}"

    # --- Internal methods (preserved from SchemaBuilder for backward compatibility) ---

    def _build_type_definition(self, entity_cfg) -> str:
        """Generate GraphQL type definition for a single entity."""
        fields = []

        try:
            type_hints = get_type_hints(entity_cfg.kls)
        except Exception:
            type_hints = {}

        # Process scalar fields
        for field_name, field_type in type_hints.items():
            if field_name.startswith('__'):
                continue

            gql_type = self._map_python_type_to_gql(field_type)
            fields.append(f"  {field_name}: {gql_type}")

        # Process relationships
        for rel in entity_cfg.relationships:
            if isinstance(rel, Relationship):
                if not hasattr(rel, 'default_field_name') or not rel.default_field_name:
                    continue

                field_name = rel.default_field_name
                target_kls = rel.target_kls
                origin = get_origin(target_kls)

                if origin is list:
                    args = get_args(target_kls)
                    if args:
                        target_name = args[0].__name__
                    else:
                        continue
                else:
                    target_name = target_kls.__name__

                if rel.load_many:
                    gql_type = f"[{target_name}]!"
                else:
                    gql_type = target_name
                fields.append(f"  {field_name}: {gql_type}")

        return f"type {entity_cfg.kls.__name__} {{\n" + "\n".join(fields) + "\n}"

    def _build_type_definition_for_class(self, kls: type) -> str:
        """Generate GraphQL type definition for any Pydantic BaseModel class."""
        fields = []

        try:
            type_hints = get_type_hints(kls)
        except Exception:
            type_hints = {}

        for field_name, field_type in type_hints.items():
            if field_name.startswith('__'):
                continue

            gql_type = self._map_python_type_to_gql(field_type)
            fields.append(f"  {field_name}: {gql_type}")

        return f"type {kls.__name__} {{\n" + "\n".join(fields) + "\n}"

    def _build_input_definition(self, kls: type) -> str:
        """Generate GraphQL Input type definition."""
        fields = []

        try:
            type_hints = get_type_hints(kls)
        except Exception:
            type_hints = {}

        for field_name, field_type in type_hints.items():
            if field_name.startswith('__'):
                continue

            gql_type = self._map_python_type_to_gql_for_input(field_type)
            fields.append(f"  {field_name}: {gql_type}")

        return f"input {kls.__name__} {{\n" + "\n".join(fields) + "\n}"

    def _map_python_type_to_gql(self, python_type: type) -> str:
        """Map Python type to GraphQL type string."""
        core_types = get_core_types(python_type)
        if not core_types:
            return "String!"

        core_type = core_types[0]
        origin = get_origin(python_type)

        # Handle ForwardRef
        from typing import ForwardRef
        if isinstance(core_type, ForwardRef):
            type_name = core_type.__forward_arg__
            entity_kls = self._get_entity_by_name(type_name)
            if entity_kls:
                core_type = entity_kls

        # Check if it's list[T]
        is_list = origin is list or (
            hasattr(python_type, '__origin__') and
            python_type.__origin__ is list
        )

        if is_list:
            inner_gql = self._map_python_type_to_gql(core_type)
            return f"[{inner_gql}]!"
        else:
            # Check if it's an enum type first
            if is_enum_type(core_type):
                return f"{core_type.__name__}!"
            elif safe_issubclass(core_type, BaseModel):
                return f"{core_type.__name__}!"
            else:
                scalar_name = map_scalar_type(core_type)
                return f"{scalar_name}!"

    def _map_python_type_to_gql_for_input(self, python_type: type) -> str:
        """Map Python type to GraphQL type string (for input types)."""
        from typing import Union

        origin = get_origin(python_type)

        # Handle Optional[T]
        if origin is Union:
            args = get_args(python_type)
            non_none_args = [a for a in args if a is not type(None)]
            if non_none_args:
                inner_gql = self._map_python_type_to_gql_for_input(non_none_args[0])
                return inner_gql.rstrip('!')

        # Handle list[T]
        if origin is list:
            args = get_args(python_type)
            if args:
                inner_gql = self._map_python_type_to_gql_for_input(args[0])
                if not inner_gql.endswith('!'):
                    inner_gql = inner_gql + '!'
                return f"[{inner_gql}]!"
            return "[String!]!"

        core_types = get_core_types(python_type)
        if not core_types:
            return "String!"

        core_type = core_types[0]

        # Handle enum types
        if is_enum_type(core_type):
            return f"{core_type.__name__}!"
        elif safe_issubclass(core_type, BaseModel):
            return f"{core_type.__name__}!"
        else:
            scalar_name = map_scalar_type(core_type)
            return f"{scalar_name}!"

    def _get_entity_by_name(self, name: str):
        """Find entity class by name from ERD."""
        for cfg in self.er_diagram.configs:
            if cfg.kls.__name__ == name:
                return cfg.kls
        return None

    def _extract_query_methods(self, entity: type) -> List[Dict]:
        """Extract all @query decorated methods."""
        methods = []

        for name, method in entity.__dict__.items():
            actual_method = method
            if isinstance(method, classmethod):
                actual_method = method.__func__

            if not hasattr(actual_method, '_pydantic_resolve_query'):
                continue

            try:
                sig = inspect.signature(actual_method)
            except Exception:
                continue

            params = []
            for param_name, param in sig.parameters.items():
                if param_name in ('self', 'cls'):
                    continue

                try:
                    gql_type = self._map_python_type_to_gql(param.annotation)
                except Exception:
                    gql_type = 'Any'

                default = param.default
                is_required = default == inspect.Parameter.empty

                if is_required:
                    param_str = f"{param_name}: {gql_type}"
                else:
                    param_str = f"{param_name}: {gql_type.rstrip('!')}"

                params.append({
                    'name': param_name,
                    'type': gql_type,
                    'required': is_required,
                    'default': default,
                    'definition': param_str
                })

            try:
                return_type = sig.return_annotation
                gql_return_type = self._map_return_type_to_gql(return_type)
            except Exception:
                gql_return_type = 'Any'

            query_name = actual_method._pydantic_resolve_query_name
            if not query_name:
                query_name = self._convert_to_query_name(name)

            description = actual_method._pydantic_resolve_query_description or ""

            methods.append({
                'name': query_name,
                'description': description,
                'params': params,
                'return_type': gql_return_type,
                'entity': entity,
                'method': actual_method
            })

        return methods

    def _extract_mutation_methods(self, entity: type) -> List[Dict]:
        """Extract all @mutation decorated methods."""
        methods = []

        for name, method in entity.__dict__.items():
            actual_method = method
            if isinstance(method, classmethod):
                actual_method = method.__func__

            if not hasattr(actual_method, '_pydantic_resolve_mutation'):
                continue

            try:
                sig = inspect.signature(actual_method)
            except Exception:
                continue

            params = []
            for param_name, param in sig.parameters.items():
                if param_name in ('self', 'cls'):
                    continue

                try:
                    gql_type = self._map_python_type_to_gql(param.annotation)
                except Exception:
                    gql_type = 'Any'

                default = param.default
                is_required = default == inspect.Parameter.empty

                if is_required:
                    param_str = f"{param_name}: {gql_type}"
                else:
                    param_str = f"{param_name}: {gql_type.rstrip('!')}"

                params.append({
                    'name': param_name,
                    'type': gql_type,
                    'required': is_required,
                    'default': default,
                    'definition': param_str
                })

            try:
                return_type = sig.return_annotation
                gql_return_type = self._map_return_type_to_gql(return_type)
            except Exception:
                gql_return_type = 'Any'

            mutation_name = actual_method._pydantic_resolve_mutation_name
            if not mutation_name:
                mutation_name = self._convert_to_mutation_name(name)

            description = actual_method._pydantic_resolve_mutation_description or ""

            methods.append({
                'name': mutation_name,
                'description': description,
                'params': params,
                'return_type': gql_return_type,
                'entity': entity,
                'method': actual_method
            })

        return methods

    def _build_query_def(self, method_info: Dict) -> str:
        """Build single query definition."""
        name = method_info['name']
        params_str = ""
        if method_info['params']:
            params = ", ".join(p['definition'] for p in method_info['params'])
            params_str = f"({params})"
        return f"{name}{params_str}: {method_info['return_type']}"

    def _build_mutation_def(self, method_info: Dict) -> str:
        """Build single mutation definition."""
        name = method_info['name']
        params_str = ""
        if method_info['params']:
            params = ", ".join(p['definition'] for p in method_info['params'])
            params_str = f"({params})"
        return f"{name}{params_str}: {method_info['return_type']}"

    def _map_return_type_to_gql(self, return_type: type) -> str:
        """Map return type to GraphQL type."""
        core_types = get_core_types(return_type)
        if not core_types:
            return self._map_python_type_to_gql(return_type)

        core_type = core_types[0]
        origin = get_origin(return_type)

        if origin is list:
            inner_gql = self._map_python_type_to_gql(core_type)
            return f"[{inner_gql}]"

        return self._map_python_type_to_gql(return_type)

    def _convert_to_query_name(self, method_name: str) -> str:
        """Convert method name to GraphQL query name."""
        for prefix in ['get_', 'fetch_', 'find_', 'query_']:
            if method_name.startswith(prefix):
                method_name = method_name[len(prefix):]
                break
        return method_name

    def _convert_to_mutation_name(self, method_name: str) -> str:
        """Convert method name to GraphQL mutation name (camelCase)."""
        components = method_name.split('_')
        return components[0] + ''.join(word.capitalize() for word in components[1:])

    def _validate_all_entities(self) -> None:
        """Validate field name conflicts for all entities."""
        for entity_cfg in self.er_diagram.configs:
            self._validate_entity_fields(entity_cfg)

    def _validate_entity_fields(self, entity_cfg) -> None:
        """Validate field conflicts for a single entity."""
        try:
            scalar_fields = set(get_type_hints(entity_cfg.kls).keys())
        except Exception:
            scalar_fields = set()

        relationship_fields = set()
        for rel in entity_cfg.relationships:
            if isinstance(rel, Relationship) and rel.default_field_name:
                relationship_fields.add(rel.default_field_name)

        conflicts = scalar_fields & relationship_fields
        if conflicts:
            field_name = next(iter(conflicts))
            raise FieldNameConflictError(
                message=f"Field name conflict in {entity_cfg.kls.__name__}: '{field_name}'",
                entity_name=entity_cfg.kls.__name__,
                field_name=field_name,
                conflict_type="SCALAR_CONFLICT"
            )

    def _collect_nested_pydantic_types(self, processed_types: set) -> set:
        """Recursively collect all nested Pydantic BaseModel types."""
        nested_types = set()
        types_to_check = list(processed_types)

        while types_to_check:
            current_type = types_to_check.pop()

            try:
                type_hints = get_type_hints(current_type)
            except Exception:
                continue

            for field_type in type_hints.values():
                core_types = get_core_types(field_type)

                for core_type in core_types:
                    if safe_issubclass(core_type, BaseModel):
                        if core_type not in processed_types and core_type not in nested_types:
                            nested_types.add(core_type)
                            types_to_check.append(core_type)

        return nested_types

    def _collect_input_types(self) -> set:
        """Collect all BaseModel types from method parameters as Input Types."""
        input_types = set()
        visited = set()

        def collect_from_type(param_type):
            core_types = get_core_types(param_type)

            for core_type in core_types:
                if safe_issubclass(core_type, BaseModel):
                    type_name = core_type.__name__
                    if type_name not in visited:
                        visited.add(type_name)
                        input_types.add(core_type)

                        try:
                            type_hints = get_type_hints(core_type)
                            for field_type in type_hints.values():
                                collect_from_type(field_type)
                        except Exception:
                            pass

        for entity_cfg in self.er_diagram.configs:
            query_methods = self._extract_query_methods(entity_cfg.kls)
            for method_info in query_methods:
                method = method_info.get('method')
                if method:
                    try:
                        sig = inspect.signature(method)
                        for param_name, param in sig.parameters.items():
                            if param_name in ('self', 'cls'):
                                continue
                            if param.annotation != inspect.Parameter.empty:
                                collect_from_type(param.annotation)
                    except Exception:
                        pass

            mutation_methods = self._extract_mutation_methods(entity_cfg.kls)
            for method_info in mutation_methods:
                method = method_info.get('method')
                if method:
                    try:
                        sig = inspect.signature(method)
                        for param_name, param in sig.parameters.items():
                            if param_name in ('self', 'cls'):
                                continue
                            if param.annotation != inspect.Parameter.empty:
                                collect_from_type(param.annotation)
                    except Exception:
                        pass

        return input_types

    def _build_enum_definition(self, enum_class: type) -> str:
        """Generate GraphQL enum definition.

        Args:
            enum_class: Python Enum class

        Returns:
            GraphQL enum definition string
        """
        values = get_enum_names(enum_class)
        if not values:
            return ""
        values_str = "\n".join(f"  {v}" for v in values)
        return f"enum {enum_class.__name__} {{\n{values_str}\n}}"

    def _collect_enum_types(self, kls: type) -> set:
        """Collect all enum types used in entity fields.

        Args:
            kls: Pydantic BaseModel class

        Returns:
            Set of enum types found in the class
        """
        enums = set()
        try:
            type_hints = get_type_hints(kls)
        except Exception:
            return enums

        for field_name, field_type in type_hints.items():
            if field_name.startswith('__'):
                continue
            core_types_list = get_core_types(field_type)
            for core_type in core_types_list:
                if is_enum_type(core_type):
                    enums.add(core_type)
        return enums

    def _add_enum_definitions(self, kls: type, enum_defs: List[str], processed_enums: Set[str]) -> None:
        """Collect and add enum definitions from a class.

        Args:
            kls: Pydantic BaseModel class
            enum_defs: List to append enum definition strings
            processed_enums: Set of already processed enum names
        """
        enum_types = self._collect_enum_types(kls)
        for enum_type in enum_types:
            if enum_type.__name__ not in processed_enums:
                enum_defs.append(self._build_enum_definition(enum_type))
                processed_enums.add(enum_type.__name__)
