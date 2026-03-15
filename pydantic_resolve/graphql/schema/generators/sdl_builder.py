"""
SDL (Schema Definition Language) builder.

This module builds GraphQL SDL strings from ErDiagram,
using the unified type collection and mapping logic.
"""

import inspect
from typing import ForwardRef, get_args, get_origin, get_type_hints

from pydantic import BaseModel

from pydantic_resolve.graphql.schema.generators.base import SchemaGenerator
from pydantic_resolve.utils.class_util import safe_issubclass
from pydantic_resolve.utils.er_diagram import Relationship, MultipleRelationship
from pydantic_resolve.utils.types import get_core_types
from pydantic_resolve.graphql.type_mapping import map_scalar_type, is_enum_type, get_enum_names
from pydantic_resolve.graphql.exceptions import FieldNameConflictError


class SDLBuilder(SchemaGenerator):
    """
    Builds GraphQL SDL (Schema Definition Language) strings.

    This is the refactored implementation that uses the unified
    type collection and mapping logic.
    """

    def generate(self) -> str:
        """
        Build complete GraphQL Schema.

        Returns:
            GraphQL Schema string
        """
        # Runtime field conflict validation
        if self.validate_conflicts:
            self._validate_all_entities()

        enum_defs: list[str] = []
        input_defs: list[str] = []
        type_defs: list[str] = []
        query_defs: list[str] = []
        mutation_defs: list[str] = []
        processed_types = set()
        processed_input_types = set()
        processed_enums = set()

        # Build all entity types
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

    def format_type(self, type_info):
        """Format a type definition as SDL string.

        Note: This method exists to satisfy the abstract base class requirement.
        SDLBuilder uses its own internal methods for type generation.
        """
        raise NotImplementedError(
            "SDLBuilder does not use format_type(). "
            "Use generate() or generate_operation_sdl() instead."
        )

    def format_field(self, field_info):
        """Format a field definition as SDL string.

        Note: This method exists to satisfy the abstract base class requirement.
        SDLBuilder uses its own internal methods for field generation.
        """
        raise NotImplementedError(
            "SDLBuilder does not use format_field(). "
            "Use generate() or generate_operation_sdl() instead."
        )

    # --- Internal methods (preserved from SchemaBuilder for backward compatibility) ---

    def _build_type_definition(self, entity_cfg) -> str:
        """Generate GraphQL type definition for a single entity."""
        fields = []

        try:
            type_hints = get_type_hints(entity_cfg.kls)
        except Exception:
            type_hints = {}

        # Get relationship field names to skip them in scalar field processing
        relationship_field_names = set()
        for rel in entity_cfg.relationships:
            if isinstance(rel, Relationship):
                if hasattr(rel, 'default_field_name') and rel.default_field_name:
                    relationship_field_names.add(rel.default_field_name)
            elif isinstance(rel, MultipleRelationship):
                for link in rel.links:
                    if link.default_field_name:
                        relationship_field_names.add(link.default_field_name)

        # Process scalar fields (skip relationship fields)
        for field_name, field_type in type_hints.items():
            if field_name.startswith('__'):
                continue
            if field_name in relationship_field_names:
                continue

            gql_type = self._map_python_type_to_gql(field_type)
            fields.append(f"  {field_name}: {gql_type}")

        # Process relationships using unified type mapping
        for rel in entity_cfg.relationships:
            if isinstance(rel, Relationship):
                if hasattr(rel, 'default_field_name') and rel.default_field_name:
                    field_name = rel.default_field_name
                    gql_type = self._map_python_type_to_gql(rel.target_kls)
                    fields.append(f"  {field_name}: {gql_type}")
            elif isinstance(rel, MultipleRelationship):
                for link in rel.links:
                    if link.default_field_name:
                        field_name = link.default_field_name
                        gql_type = self._map_python_type_to_gql(rel.target_kls)
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

            gql_type = self._map_python_type_to_gql(field_type, is_input=True)
            fields.append(f"  {field_name}: {gql_type}")

        return f"input {kls.__name__} {{\n" + "\n".join(fields) + "\n}"

    def _map_python_type_to_gql(self, python_type: type, is_input: bool = False) -> str:
        """Map Python type to GraphQL type string.

        Args:
            python_type: Python type to map
            is_input: If True, Optional[T] will not have ! (for input types)

        Returns:
            GraphQL type string with appropriate nullability
        """
        from typing import ForwardRef, Union

        origin = get_origin(python_type)

        # Handle Optional[T] (Union[T, None])
        if origin is Union:
            args = get_args(python_type)
            non_none_args = [a for a in args if a is not type(None)]
            if non_none_args:
                inner_gql = self._map_python_type_to_gql(non_none_args[0], is_input)
                # For input types, Optional fields should not have !
                if is_input:
                    return inner_gql.rstrip('!')
                return inner_gql

        # Check if it's list[T]
        is_list = origin is list or (
            hasattr(python_type, '__origin__') and
            python_type.__origin__ is list
        )

        if is_list:
            args = get_args(python_type)
            if args:
                inner_gql = self._map_python_type_to_gql(args[0], is_input)
                # List elements should always have ! in GraphQL
                if not inner_gql.endswith('!'):
                    inner_gql = inner_gql + '!'
                return f"[{inner_gql}]!"
            return "[String!]!"

        core_types = get_core_types(python_type)
        if not core_types:
            return "String!"

        core_type = core_types[0]

        # Handle ForwardRef
        if isinstance(core_type, ForwardRef):
            type_name = core_type.__forward_arg__
            entity_kls = self._get_entity_by_name(type_name)
            if entity_kls:
                core_type = entity_kls

        # Handle string type names that correspond to entity types
        if isinstance(core_type, str):
            entity_kls = self._get_entity_by_name(core_type)
            if entity_kls:
                core_type = entity_kls

        # Map the core type
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

    def _extract_query_methods(self, entity: type) -> list[dict]:
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

            # Generate GraphQL query name using entity_name + method_name
            from pydantic_resolve.graphql.utils.naming import to_graphql_field_name
            query_name = to_graphql_field_name(entity.__name__, name)

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

    def _extract_mutation_methods(self, entity: type) -> list[dict]:
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

            # Generate GraphQL mutation name using entity_name + method_name
            from pydantic_resolve.graphql.utils.naming import to_graphql_field_name
            mutation_name = to_graphql_field_name(entity.__name__, name)

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

    def _build_query_def(self, method_info: dict) -> str:
        """Build single query definition."""
        name = method_info['name']
        params_str = ""
        if method_info['params']:
            params = ", ".join(p['definition'] for p in method_info['params'])
            params_str = f"({params})"
        return f"{name}{params_str}: {method_info['return_type']}"

    def _build_mutation_def(self, method_info: dict) -> str:
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
        """Recursively collect all nested Pydantic BaseModel types,
        including types from Relationship.target_kls and MultipleRelationship.target_kls."""
        nested_types = set()
        types_to_check = list(processed_types)

        # Add target_kls from relationships to types_to_check
        for entity_cfg in self.er_diagram.configs:
            for rel in entity_cfg.relationships:
                if isinstance(rel, (Relationship, MultipleRelationship)):
                    # get_core_types handles list[T] and Optional[T] unwrapping
                    for target_class in get_core_types(rel.target_kls):
                        if safe_issubclass(target_class, BaseModel):
                            if target_class not in processed_types and target_class not in nested_types:
                                nested_types.add(target_class)
                                types_to_check.append(target_class)

        # Recursively scan all types (existing logic handles nested fields)
        while types_to_check:
            current_type = types_to_check.pop()

            try:
                type_hints = get_type_hints(current_type)
            except Exception:
                continue

            for field_type in type_hints.values():
                for core_type in get_core_types(field_type):
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

    def _add_enum_definitions(self, kls: type, enum_defs: list[str], processed_enums: set[str]) -> None:
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

    def generate_operation_sdl(
        self, operation_name: str, operation_type: str = "Query"
    ) -> str | None:
        """Generate SDL for a single operation and its related types.

        This method is used for MCP progressive disclosure, It generates
        the SDL for a specific query or mutation along with all related
        type definitions.

        Args:
            operation_name: Name of the GraphQL operation (e.g., "userEntityGetAll")
            operation_type: "Query" or "Mutation" (default: "Query")

        Returns:
            SDL string for the operation and related types, or None if not found.

        Example:
            >>> generator.generate_operation_sdl("userEntityGetAll", "Query")
            '# Query\\nuserEntityGetAll(limit: Int, offset: Int): [UserEntity!]!\\n\\n# Related Types\\ntype UserEntity { ... }'
        """
        # Find the operation method
        method_info = self._find_operation_method(operation_name, operation_type)
        if not method_info:
            return None

        # Collect related entity types
        related_entities = self._collect_related_entities_from_method(method_info)

        # Build SDL parts
        parts = []

        # Build operation definition
        if operation_type == "Query":
            field_def = self._build_query_def(method_info)
        else:
            field_def = self._build_mutation_def(method_info)
        parts.append(f"# {operation_type}\n{field_def}")

        # Build related type definitions
        if related_entities:
            type_defs = []
            processed_types = set()
            processed_enums = set()

            for entity in related_entities:
                if entity.__name__ not in processed_types:
                    type_defs.append(self._build_entity_type(entity))
                    processed_types.add(entity.__name__)
                    # Collect enums from this entity
                    self._add_enum_definitions(entity, type_defs, processed_enums)

            if type_defs:
                parts.append("# Related Types\n" + "\n\n".join(type_defs))

        return "\n\n".join(parts)

    def _find_operation_method(
        self, operation_name: str, operation_type: str
    ) -> dict | None:
        """Find method info for a given operation name.

        Args:
            operation_name: Name of the GraphQL operation
            operation_type: "Query" or "Mutation"

        Returns:
            Method info dictionary or None if not found
        """
        for entity_cfg in self.er_diagram.configs:
            if operation_type == "Query":
                methods = self._extract_query_methods(entity_cfg.kls)
            else:
                methods = self._extract_mutation_methods(entity_cfg.kls)

            for method in methods:
                if method['name'] == operation_name:
                    return method
        return None

    def _collect_related_entities_from_method(self, method_info: dict) -> set[type]:
        """Collect all related entity types from a method's return type and parameters.

        Args:
            method_info: Method info dictionary

        Returns:
            Set of related entity classes
        """
        related_entities = set()
        visited = set()

        def collect_from_type(python_type) -> None:
            """Recursively collect entity types from a type hint."""
            core_types = get_core_types(python_type)

            for core_type in core_types:
                # Handle ForwardRef by resolving to actual class
                if isinstance(core_type, ForwardRef):
                    type_name = core_type.__forward_arg__
                    resolved = self._get_entity_by_name(type_name)
                    if resolved:
                        core_type = resolved
                    else:
                        continue

                # Handle string type names that correspond to entity types
                if isinstance(core_type, str):
                    resolved = self._get_entity_by_name(core_type)
                    if resolved:
                        core_type = resolved
                    else:
                        continue

                if safe_issubclass(core_type, BaseModel):
                    type_name = core_type.__name__
                    if type_name not in visited:
                        # Check if it's an entity in our ER diagram
                        for entity_cfg in self.er_diagram.configs:
                            if entity_cfg.kls == core_type:
                                visited.add(type_name)
                                related_entities.add(core_type)

                                # Recursively collect from entity fields
                                try:
                                    type_hints = get_type_hints(core_type)
                                    for field_type in type_hints.values():
                                        collect_from_type(field_type)
                                except Exception:
                                    pass

                                # Collect from relationships with default_field_name
                                for rel in entity_cfg.relationships:
                                    if isinstance(rel, Relationship):
                                        if rel.default_field_name:
                                            collect_from_type(rel.target_kls)
                                    elif isinstance(rel, MultipleRelationship):
                                        for link in rel.links:
                                            if link.default_field_name:
                                                collect_from_type(rel.target_kls)
                                                break  # target_kls is the same for all links
                                break  # Found the entity, no need to check other configs

        # Collect from return type
        method = method_info.get('method')
        if method:
            try:
                sig = inspect.signature(method)
                return_type = sig.return_annotation
                if return_type != inspect.Signature.empty:
                    collect_from_type(return_type)
            except Exception:
                pass

            # Collect from parameter types
            try:
                sig = inspect.signature(method)
                for param_name, param in sig.parameters.items():
                    if param_name in ('self', 'cls'):
                        continue
                    if param.annotation != inspect.Parameter.empty:
                        collect_from_type(param.annotation)
            except Exception:
                pass

        return related_entities

    def _build_entity_type(self, entity: type) -> str:
        """Build GraphQL type definition for an entity.

        Args:
            entity: Pydantic BaseModel class

        Returns:
            GraphQL type definition string
        """
        fields = []

        # Get entity config for relationship filtering
        entity_cfg = None
        for cfg in self.er_diagram.configs:
            if cfg.kls == entity:
                entity_cfg = cfg
                break

        # Process scalar fields
        try:
            type_hints = get_type_hints(entity)
        except Exception:
            type_hints = {}

        for field_name, field_type in type_hints.items():
            if field_name.startswith('__'):
                continue

            # Skip relationship fields
            if entity_cfg and self._is_relationship_field(entity_cfg, field_name):
                continue

            gql_type = self._map_python_type_to_gql(field_type)
            fields.append(f"  {field_name}: {gql_type}")

        # Process relationship fields
        if entity_cfg:
            for rel in entity_cfg.relationships:
                if isinstance(rel, Relationship):
                    if hasattr(rel, 'default_field_name') and rel.default_field_name:
                        field_name = rel.default_field_name
                        gql_type = self._map_python_type_to_gql(rel.target_kls)
                        fields.append(f"  {field_name}: {gql_type}")
                elif isinstance(rel, MultipleRelationship):
                    for link in rel.links:
                        if link.default_field_name:
                            field_name = link.default_field_name
                            gql_type = self._map_python_type_to_gql(rel.target_kls)
                            fields.append(f"  {field_name}: {gql_type}")

        # Build type definition
        type_def = f"type {entity.__name__} {{\n" + "\n".join(fields) + "\n}"
        return type_def

    def _is_relationship_field(self, entity_cfg, field_name: str) -> bool:
        """Check if a field name is a relationship field.

        Args:
            entity_cfg: Entity configuration
            field_name: Field name to check

        Returns:
            True if the field is a relationship field
        """
        for rel in entity_cfg.relationships:
            if isinstance(rel, Relationship):
                if hasattr(rel, 'default_field_name') and rel.default_field_name == field_name:
                    return True
            elif isinstance(rel, MultipleRelationship):
                for link in rel.links:
                    if link.default_field_name == field_name:
                        return True
        return False
