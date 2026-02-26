"""
GraphQL Schema generator from ERD and @query decorated methods.
"""

import inspect
from typing import Dict, List, get_args, get_origin, get_type_hints
from pydantic import BaseModel

from ..utils.er_diagram import ErDiagram, Relationship
from ..utils.class_util import safe_issubclass
from ..utils.types import get_core_types
from .exceptions import FieldNameConflictError
from .type_mapping import map_scalar_type


class SchemaBuilder:
    """Generate GraphQL Schema from ERD and @query decorated methods"""

    def __init__(self, er_diagram: ErDiagram, validate_conflicts: bool = True):
        """
        Args:
            er_diagram: Entity relationship diagram
            validate_conflicts: Whether to validate field name conflicts (default True)
        """
        self.er_diagram = er_diagram
        self.validate_conflicts = validate_conflicts

    def build_schema(self) -> str:
        """
        Generate complete GraphQL Schema

        Returns:
            GraphQL Schema string
        """
        # Runtime field conflict validation (double guarantee)
        if self.validate_conflicts:
            self._validate_all_entities()

        input_defs = []  # Input types
        type_defs = []   # Output types
        query_defs = []
        mutation_defs = []
        processed_types = set()  # Track processed types to avoid duplication
        processed_input_types = set()  # Track processed input types

        # Generate all entity types
        for entity_cfg in self.er_diagram.configs:
            type_def = self._build_type_definition(entity_cfg)
            type_defs.append(type_def)
            processed_types.add(entity_cfg.kls)

            # Extract @query methods for this entity
            query_methods = self._extract_query_methods(entity_cfg.kls)
            for method in query_methods:
                query_defs.append(self._build_query_def(method))

            # Extract @mutation methods for this entity
            mutation_methods = self._extract_mutation_methods(entity_cfg.kls)
            for method in mutation_methods:
                mutation_defs.append(self._build_mutation_def(method))

        # Collect and generate all nested Pydantic types
        nested_types = self._collect_nested_pydantic_types(processed_types)
        for nested_type in nested_types:
            if nested_type not in processed_types:
                type_def = self._build_type_definition_for_class(nested_type)
                type_defs.append(type_def)
                processed_types.add(nested_type)

        # Collect and generate all Input Types (from method parameters)
        input_types = self._collect_input_types()
        for input_type in input_types:
            if input_type not in processed_input_types:
                input_def = self._build_input_definition(input_type)
                input_defs.append(input_def)
                processed_input_types.add(input_type)

        # Assemble complete Schema: input types first, then output types
        schema_parts = []

        # Input types
        if input_defs:
            schema_parts.append("\n".join(input_defs))

        # Output types
        if type_defs:
            schema_parts.append("\n".join(type_defs))

        schema = "\n\n".join(schema_parts) + "\n\n"

        # Query type
        schema += "type Query {\n"
        if query_defs:
            schema += "\n".join(f"  {qd}" for qd in query_defs) + "\n"
        schema += "}\n\n"

        # Only generate Mutation type if there are mutations
        if mutation_defs:
            schema += "type Mutation {\n"
            schema += "\n".join(f"  {md}" for md in mutation_defs) + "\n"
            schema += "}\n"

        return schema

    def _build_type_definition(self, entity_cfg) -> str:
        """Generate GraphQL type definition for a single entity"""
        fields = []

        # Get all type hints for the entity
        try:
            type_hints = get_type_hints(entity_cfg.kls)
        except Exception:
            type_hints = {}

        # Process scalar fields
        for field_name, field_type in type_hints.items():
            if field_name.startswith('__'):
                continue

            # Map Python type to GraphQL type
            gql_type = self._map_python_type_to_gql(field_type)
            fields.append(f"  {field_name}: {gql_type}")

        # Process relationships (from __relationships__)
        for rel in entity_cfg.relationships:
            if isinstance(rel, Relationship):
                # Only relationships with default_field_name are exposed to GraphQL
                if not hasattr(rel, 'default_field_name') or not rel.default_field_name:
                    continue

                field_name = rel.default_field_name

                # Handle generic types (e.g., list[PostEntity])
                target_kls = rel.target_kls
                origin = get_origin(target_kls)

                if origin is list:
                    # list[PostEntity] -> PostEntity
                    args = get_args(target_kls)
                    if args:
                        target_name = args[0].__name__
                    else:
                        continue  # Cannot determine element type, skip
                else:
                    target_name = target_kls.__name__

                if rel.load_many:
                    gql_type = f"[{target_name}]!"
                else:
                    gql_type = target_name
                fields.append(f"  {field_name}: {gql_type}")

        return f"type {entity_cfg.kls.__name__} {{\n" + "\n".join(fields) + "\n}"

    def _extract_query_methods(self, entity: type) -> List[Dict]:
        """
        Extract all @query decorated methods from an Entity

        Returns:
            List of method information, each element contains:
            - name: GraphQL query name
            - description: Query description
            - params: Parameter list
            - return_type: Return type
            - entity: Entity class
            - method: Method object
        """
        methods = []

        for name, method in entity.__dict__.items():
            # Handle classmethod - access underlying function
            actual_method = method
            if isinstance(method, classmethod):
                actual_method = method.__func__

            # Check if it has @query decorator marker
            if not hasattr(actual_method, '_pydantic_resolve_query'):
                continue

            # Get method signature
            try:
                sig = inspect.signature(actual_method)
            except Exception:
                continue

            params = []

            # Skip self/cls parameters
            for param_name, param in sig.parameters.items():
                if param_name in ('self', 'cls'):
                    continue

                # Build GraphQL parameter definition
                try:
                    gql_type = self._map_python_type_to_gql(param.annotation)
                except Exception:
                    # Cannot infer type, use Any
                    gql_type = 'Any'

                # Check if it's a required parameter
                default = param.default
                is_required = default == inspect.Parameter.empty

                # Parameter definition doesn't use $ prefix, and gql_type already includes ! suffix
                if is_required:
                    param_str = f"{param_name}: {gql_type}"
                else:
                    # Remove trailing ! to indicate optional
                    param_str = f"{param_name}: {gql_type.rstrip('!')}"

                params.append({
                    'name': param_name,
                    'type': gql_type,
                    'required': is_required,
                    'default': default,
                    'definition': param_str
                })

            # Determine return type
            try:
                return_type = sig.return_annotation
                gql_return_type = self._map_return_type_to_gql(return_type)
            except Exception:
                # Cannot infer return type
                gql_return_type = 'Any'

            # Determine GraphQL query name
            query_name = actual_method._pydantic_resolve_query_name
            if not query_name:
                # Default: get_all → users, get_by_id → user
                query_name = self._convert_to_query_name(name)

            description = actual_method._pydantic_resolve_query_description or ""

            methods.append({
                'name': query_name,
                'description': description,
                'params': params,
                'return_type': gql_return_type,
                'entity': entity,
                'method': actual_method  # Save actual callable function (for classmethod it's __func__)
            })

        return methods

    def _extract_mutation_methods(self, entity: type) -> List[Dict]:
        """
        Extract all @mutation decorated methods from an Entity

        Returns:
            List of method information, each element contains:
            - name: GraphQL mutation name
            - description: Mutation description
            - params: Parameter list
            - return_type: Return type
            - entity: Entity class
            - method: Method object
        """
        methods = []

        for name, method in entity.__dict__.items():
            # Handle classmethod - access underlying function
            actual_method = method
            if isinstance(method, classmethod):
                actual_method = method.__func__

            # Check if it has @mutation decorator marker
            if not hasattr(actual_method, '_pydantic_resolve_mutation'):
                continue

            # Get method signature
            try:
                sig = inspect.signature(actual_method)
            except Exception:
                continue

            params = []

            # Skip self/cls parameters
            for param_name, param in sig.parameters.items():
                if param_name in ('self', 'cls'):
                    continue

                # Build GraphQL parameter definition
                try:
                    gql_type = self._map_python_type_to_gql(param.annotation)
                except Exception:
                    # Cannot infer type, use Any
                    gql_type = 'Any'

                # Check if it's a required parameter
                default = param.default
                is_required = default == inspect.Parameter.empty

                # Parameter definition doesn't use $ prefix, and gql_type already includes ! suffix
                if is_required:
                    param_str = f"{param_name}: {gql_type}"
                else:
                    # Remove trailing ! to indicate optional
                    param_str = f"{param_name}: {gql_type.rstrip('!')}"

                params.append({
                    'name': param_name,
                    'type': gql_type,
                    'required': is_required,
                    'default': default,
                    'definition': param_str
                })

            # Determine return type
            try:
                return_type = sig.return_annotation
                gql_return_type = self._map_return_type_to_gql(return_type)
            except Exception:
                # Cannot infer return type
                gql_return_type = 'Any'

            # Determine GraphQL mutation name
            mutation_name = actual_method._pydantic_resolve_mutation_name
            if not mutation_name:
                # Default: create_user -> createUser
                mutation_name = self._convert_to_mutation_name(name)

            description = actual_method._pydantic_resolve_mutation_description or ""

            methods.append({
                'name': mutation_name,
                'description': description,
                'params': params,
                'return_type': gql_return_type,
                'entity': entity,
                'method': actual_method  # Save actual callable function (for classmethod it's __func__)
            })

        return methods

    def _build_query_def(self, method_info: Dict) -> str:
        """Build single query definition"""
        name = method_info['name']

        # Build parameters section
        params_str = ""
        if method_info['params']:
            params = ", ".join(p['definition'] for p in method_info['params'])
            params_str = f"({params})"

        # Build return type
        return_type = method_info['return_type']

        return f"{name}{params_str}: {return_type}"

    def _build_mutation_def(self, method_info: Dict) -> str:
        """Build single mutation definition"""
        name = method_info['name']

        # Build parameters section
        params_str = ""
        if method_info['params']:
            params = ", ".join(p['definition'] for p in method_info['params'])
            params_str = f"({params})"

        # Build return type
        return_type = method_info['return_type']

        return f"{name}{params_str}: {return_type}"

    def _map_python_type_to_gql(self, python_type: type) -> str:
        """
        Map Python type to GraphQL type

        Args:
            python_type: Python type

        Returns:
            GraphQL type string (e.g., "String!", "[Int]!")
        """
        # Use get_core_types to handle all wrapper types (Optional, list, Annotated, etc.)
        core_types = get_core_types(python_type)
        if not core_types:
            return "String!"  # Default to String

        core_type = core_types[0]
        origin = get_origin(python_type)

        # Check if it's list[T]
        is_list = origin is list or (
            hasattr(python_type, '__origin__') and
            python_type.__origin__ is list
        )

        if is_list:
            # list[T] -> [T!]!
            inner_gql = self._map_python_type_to_gql(core_type)
            return f"[{inner_gql}]!"
        else:
            # T -> T!
            if safe_issubclass(core_type, BaseModel):
                return f"{core_type.__name__}!"
            else:
                # Scalar type
                scalar_name = map_scalar_type(core_type)
                return f"{scalar_name}!"

    def _map_return_type_to_gql(self, return_type: type) -> str:
        """Map return type to GraphQL type"""
        # Use get_core_types to handle all wrapper types
        core_types = get_core_types(return_type)
        if not core_types:
            return self._map_python_type_to_gql(return_type)

        core_type = core_types[0]
        origin = get_origin(return_type)

        # Handle List[X]
        if origin is list:
            inner_gql = self._map_python_type_to_gql(core_type)
            return f"[{inner_gql}]"

        # Default handling
        return self._map_python_type_to_gql(return_type)

    def _convert_to_query_name(self, method_name: str) -> str:
        """
        Convert method name to GraphQL query name

        Examples:
            get_all -> all
            get_by_id -> by_id
            fetch_users -> users
        """
        # Remove common prefixes
        for prefix in ['get_', 'fetch_', 'find_', 'query_']:
            if method_name.startswith(prefix):
                method_name = method_name[len(prefix):]
                break

        # Convert to camelCase
        return method_name

    def _convert_to_mutation_name(self, method_name: str) -> str:
        """
        Convert method name to GraphQL mutation name

        Examples:
            create_user -> createUser
            update_user -> updateUser
            delete_post -> deletePost
            add_comment -> addComment
        """
        # Convert snake_case to camelCase
        components = method_name.split('_')
        return components[0] + ''.join(word.capitalize() for word in components[1:])

    def _validate_all_entities(self) -> None:
        """Validate field name conflicts for all entities (runtime check)."""
        for entity_cfg in self.er_diagram.configs:
            self._validate_entity_fields(entity_cfg)

    def _validate_entity_fields(self, entity_cfg) -> None:
        """Validate field conflicts for a single entity."""
        # Collect all fields (scalar + relationship)
        try:
            scalar_fields = set(get_type_hints(entity_cfg.kls).keys())
        except Exception:
            scalar_fields = set()

        relationship_fields = set()
        for rel in entity_cfg.relationships:
            if isinstance(rel, Relationship) and rel.default_field_name:
                relationship_fields.add(rel.default_field_name)

        # Check intersection
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
        """
        Recursively collect all nested Pydantic BaseModel types

        Args:
            processed_types: Set of already processed types

        Returns:
            Set of all discovered nested Pydantic types
        """
        nested_types = set()
        types_to_check = list(processed_types)

        while types_to_check:
            current_type = types_to_check.pop()

            # Get all type hints for current type
            try:
                type_hints = get_type_hints(current_type)
            except Exception:
                continue

            for field_type in type_hints.values():
                # Use get_core_types to handle all wrapper types
                core_types = get_core_types(field_type)

                for core_type in core_types:
                    # Check if it's Pydantic BaseModel
                    if safe_issubclass(core_type, BaseModel):
                        if core_type not in processed_types and core_type not in nested_types:
                            nested_types.add(core_type)
                            types_to_check.append(core_type)

        return nested_types

    def _build_type_definition_for_class(self, kls: type) -> str:
        """
        Generate GraphQL type definition for any Pydantic BaseModel class

        Args:
            kls: Pydantic BaseModel class

        Returns:
            GraphQL type definition string
        """
        fields = []

        # Get all type hints for the class
        try:
            type_hints = get_type_hints(kls)
        except Exception:
            type_hints = {}

        # Process all fields
        for field_name, field_type in type_hints.items():
            if field_name.startswith('__'):
                continue

            # Map Python type to GraphQL type
            gql_type = self._map_python_type_to_gql(field_type)
            fields.append(f"  {field_name}: {gql_type}")

        return f"type {kls.__name__} {{\n" + "\n".join(fields) + "\n}"

    def _collect_input_types(self) -> set:
        """
        Collect all BaseModel types from method parameters as Input Types

        Returns:
            Set of all BaseModel types that need input definitions
        """
        input_types = set()
        visited = set()

        def collect_from_type(param_type):
            """Recursively collect BaseModel types"""
            # Use get_core_types to handle wrapper types
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

        # Iterate through all @query and @mutation methods for all entities
        for entity_cfg in self.er_diagram.configs:
            # Collect @query method parameter types
            query_methods = self._extract_query_methods(entity_cfg.kls)
            for method_info in query_methods:
                for param in method_info.get('params', []):
                    # Get original parameter type (from method signature)
                    method = method_info.get('method')
                    if method:
                        try:
                            sig = inspect.signature(method)
                            param_name = param['name']
                            if param_name in sig.parameters:
                                param_type = sig.parameters[param_name].annotation
                                if param_type != inspect.Parameter.empty:
                                    collect_from_type(param_type)
                        except Exception:
                            pass

            # Collect @mutation method parameter types
            mutation_methods = self._extract_mutation_methods(entity_cfg.kls)
            for method_info in mutation_methods:
                for param in method_info.get('params', []):
                    method = method_info.get('method')
                    if method:
                        try:
                            sig = inspect.signature(method)
                            param_name = param['name']
                            if param_name in sig.parameters:
                                param_type = sig.parameters[param_name].annotation
                                if param_type != inspect.Parameter.empty:
                                    collect_from_type(param_type)
                        except Exception:
                            pass

        return input_types

    def _build_input_definition(self, kls: type) -> str:
        """
        Generate GraphQL Input type definition for Pydantic BaseModel class

        Args:
            kls: Pydantic BaseModel class

        Returns:
            GraphQL input type definition string
        """
        fields = []

        # Get all type hints for the class
        try:
            type_hints = get_type_hints(kls)
        except Exception:
            type_hints = {}

        # Process all fields
        for field_name, field_type in type_hints.items():
            if field_name.startswith('__'):
                continue

            # Map Python type to GraphQL type (for input)
            gql_type = self._map_python_type_to_gql_for_input(field_type)
            fields.append(f"  {field_name}: {gql_type}")

        return f"input {kls.__name__} {{\n" + "\n".join(fields) + "\n}"

    def _map_python_type_to_gql_for_input(self, python_type: type) -> str:
        """
        Map Python type to GraphQL type (for Input types)

        Similar to _map_python_type_to_gql, but handles nested Input types

        Args:
            python_type: Python type

        Returns:
            GraphQL type string
        """
        from typing import Union

        origin = get_origin(python_type)

        # Handle Optional[T] (Union[T, None])
        if origin is Union:
            args = get_args(python_type)
            # Filter out NoneType
            non_none_args = [a for a in args if a is not type(None)]
            if non_none_args:
                # Take first non-None type, process recursively (no ! suffix since it's optional)
                inner_gql = self._map_python_type_to_gql_for_input(non_none_args[0])
                # Remove ! suffix to indicate optional
                return inner_gql.rstrip('!')

        # Handle list[T]
        if origin is list:
            args = get_args(python_type)
            if args:
                inner_gql = self._map_python_type_to_gql_for_input(args[0])
                # Ensure inner type has ! suffix
                if not inner_gql.endswith('!'):
                    inner_gql = inner_gql + '!'
                return f"[{inner_gql}]!"
            return "[String!]!"

        # Handle core types
        core_types = get_core_types(python_type)
        if not core_types:
            return "String!"

        core_type = core_types[0]

        if safe_issubclass(core_type, BaseModel):
            # Input type references other Input types
            return f"{core_type.__name__}!"
        else:
            # Scalar type
            scalar_name = map_scalar_type(core_type)
            return f"{scalar_name}!"

