"""
Introspection generator for GraphQL schema.

This module generates introspection data for GraphiQL compatibility,
using the unified type collection and mapping logic.
"""

import inspect
import re
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, get_type_hints

from pydantic import BaseModel

from pydantic_resolve.graphql.schema.generators.base import SchemaGenerator
from pydantic_resolve.graphql.schema.type_registry import TypeInfo, FieldInfo, ArgumentInfo, SCALAR_TYPES
from pydantic_resolve.utils.class_util import safe_issubclass
from pydantic_resolve.utils.er_diagram import Relationship
from pydantic_resolve.utils.types import get_core_types
from pydantic_resolve.graphql.type_mapping import map_scalar_type, is_list_type, is_enum_type, get_enum_names


class IntrospectionGenerator(SchemaGenerator):
    """
    Generates GraphQL introspection data for GraphiQL.

    This implementation uses the unified type collection logic
    from SchemaGenerator base class.
    """

    def __init__(
        self,
        er_diagram,
        query_map: Optional[Dict[str, Tuple[type, Callable]]] = None,
        mutation_map: Optional[Dict[str, Tuple[type, Callable]]] = None
    ):
        """
        Initialize the introspection generator.

        Args:
            er_diagram: Entity relationship diagram
            query_map: Mapping of query names to (entity, method) tuples
            mutation_map: Mapping of mutation names to (entity, method) tuples
        """
        super().__init__(er_diagram)
        self.query_map = query_map or {}
        self.mutation_map = mutation_map or {}
        self._collected_types: Dict[str, type] = {}
        self._input_types: Set[type] = set()

    def generate(self) -> Dict[str, Any]:
        """
        Generate full introspection schema.

        Returns:
            Introspection __schema dictionary
        """
        return {
            "queryType": {"name": "Query", "kind": "OBJECT"},
            "mutationType": {"name": "Mutation", "kind": "OBJECT"} if self.mutation_map else None,
            "subscriptionType": None,
            "types": self._get_all_introspection_types(),
            "directives": []
        }

    def format_type(self, type_info: TypeInfo) -> Dict[str, Any]:
        """Format a type definition as introspection dict."""
        result = {
            "kind": type_info.kind,
            "name": type_info.name,
            "description": type_info.description,
            "fields": None if type_info.is_input else [self.format_field(f) for f in type_info.fields.values()],
            "inputFields": [self._format_input_field(f) for f in type_info.fields.values()] if type_info.is_input else None,
            "interfaces": type_info.interfaces if not type_info.is_input else None,
            "enumValues": type_info.enumValues,
            "possibleTypes": None
        }
        return result

    def format_field(self, field_info: FieldInfo) -> Dict[str, Any]:
        """Format a field definition as introspection dict."""
        return {
            "name": field_info.name,
            "description": field_info.description,
            "args": [self._format_arg(arg) for arg in field_info.args],
            "type": self._build_type_ref(field_info),
            "isDeprecated": field_info.is_deprecated,
            "deprecationReason": field_info.deprecation_reason
        }

    # --- Main introspection methods ---

    async def execute(self, query: str) -> Dict[str, Any]:
        """
        Execute an introspection query.

        Args:
            query: GraphQL query string

        Returns:
            Introspection response with data and errors
        """
        query_info = self._parse_introspection_query(query)
        data = {}

        if query_info["requests_schema"]:
            data["__schema"] = self.generate()

        if query_info["requests_type"]:
            type_name = self._extract_type_name_from_query(query)
            if type_name:
                data["__type"] = self._get_introspection_type(type_name)

        return {"data": data, "errors": None}

    def is_introspection_query(self, query: str) -> bool:
        """Check if this is an introspection query."""
        query_stripped = query.strip()
        introspection_keywords = ["__schema", "__type", "__typename"]
        return any(keyword in query_stripped for keyword in introspection_keywords)

    # --- Internal implementation ---

    def _parse_introspection_query(self, query: str) -> Dict[str, bool]:
        """Parse introspection query and extract requested fields."""
        try:
            requests_type = "__type(" in query or '__type (' in query.replace('"', "'")
            return {
                "requests_schema": "__schema" in query,
                "requests_type": requests_type
            }
        except Exception:
            return {"requests_schema": True, "requests_type": True}

    def _extract_type_name_from_query(self, query: str) -> Optional[str]:
        """Extract type name from query."""
        match = re.search(r'__type\s*\(\s*name\s*:\s*["\']([^"\']+)["\']', query)
        if match:
            return match.group(1)
        match = re.search(r"__type\s*\(\s*name\s*:\s*'([^']+)'", query)
        if match:
            return match.group(1)
        return None

    def _get_all_introspection_types(self) -> List[Dict]:
        """Get all types for introspection."""
        types = []

        # Add scalar types (convert TypeInfo to dict format)
        for name in ["Int", "Float", "String", "Boolean", "ID"]:
            scalar = SCALAR_TYPES[name]
            types.append({
                "kind": scalar.kind,
                "name": scalar.name,
                "description": scalar.description,
                "fields": None,
                "inputFields": None,
                "interfaces": None,
                "enumValues": None,
                "possibleTypes": None
            })

        # Collect all entity types
        self._collect_all_types()

        # Add enum types (ENUM)
        collected_enums = self._collect_all_enum_types()
        for enum_class in collected_enums:
            types.append(self._build_enum_type(enum_class))

        # Add entity types (OBJECT)
        for type_name, entity in self._collected_types.items():
            types.append(self._build_object_type(entity))

        # Add input types (INPUT_OBJECT)
        for input_type in self._input_types:
            types.append(self._build_input_type(input_type))

        # Add Query type
        types.append({
            "kind": "OBJECT",
            "name": "Query",
            "description": "Root query type",
            "fields": self._get_query_fields(),
            "inputFields": None,
            "interfaces": [],
            "enumValues": None,
            "possibleTypes": None
        })

        # Add Mutation type
        if self.mutation_map:
            types.append({
                "kind": "OBJECT",
                "name": "Mutation",
                "description": "Root mutation type",
                "fields": self._get_mutation_fields(),
                "inputFields": None,
                "interfaces": [],
                "enumValues": None,
                "possibleTypes": None
            })

        return types

    def _get_introspection_type(self, type_name: str) -> Optional[Dict[str, Any]]:
        """Get introspection info for a specific type."""
        # Check scalar types (convert TypeInfo to dict format)
        if type_name in SCALAR_TYPES:
            scalar = SCALAR_TYPES[type_name]
            return {
                "kind": scalar.kind,
                "name": scalar.name,
                "description": scalar.description,
                "fields": None,
                "inputFields": None,
                "interfaces": None,
                "enumValues": None,
                "possibleTypes": None
            }

        # Collect all types
        self._collect_all_types()

        # Check enum types
        collected_enums = self._collect_all_enum_types()
        for enum_class in collected_enums:
            if enum_class.__name__ == type_name:
                return self._build_enum_type(enum_class)

        # Check entity types
        if type_name in self._collected_types:
            return self._build_object_type(self._collected_types[type_name])

        # Check input types
        for input_type in self._input_types:
            if input_type.__name__ == type_name:
                return self._build_input_type(input_type)

        # Check Query type
        if type_name == "Query":
            return {
                "kind": "OBJECT",
                "name": "Query",
                "description": "Root query type",
                "fields": self._get_query_fields(),
                "inputFields": None,
                "interfaces": [],
                "enumValues": None,
                "possibleTypes": None
            }

        # Check Mutation type
        if type_name == "Mutation" and self.mutation_map:
            return {
                "kind": "OBJECT",
                "name": "Mutation",
                "description": "Root mutation type",
                "fields": self._get_mutation_fields(),
                "inputFields": None,
                "interfaces": [],
                "enumValues": None,
                "possibleTypes": None
            }

        return None

    def _collect_all_types(self) -> None:
        """Collect all types from ERD and query/mutation maps."""
        if self._collected_types:
            return  # Already collected

        # Collect entities from ERD
        for entity_cfg in self.er_diagram.configs:
            self._collected_types[entity_cfg.kls.__name__] = entity_cfg.kls

        # Collect nested types
        nested = self._collect_nested_pydantic_types(list(self._collected_types.values()))
        for name, cls in nested.items():
            if name not in self._collected_types:
                self._collected_types[name] = cls

        # Collect input types
        self._input_types = self._collect_input_types_from_maps()

    def _collect_nested_pydantic_types(
        self,
        entities: List[type],
        visited: Optional[Set[str]] = None
    ) -> Dict[str, type]:
        """Recursively collect all Pydantic BaseModel types."""
        if visited is None:
            visited = set()

        collected: Dict[str, type] = {}

        for entity in entities:
            type_name = entity.__name__
            if type_name in visited:
                continue
            visited.add(type_name)

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

        if collected:
            nested = self._collect_nested_pydantic_types(list(collected.values()), visited)
            collected.update(nested)

        return collected

    def _collect_input_types_from_maps(self) -> Set[type]:
        """Collect input types from query/mutation maps."""
        input_types: Set[type] = set()
        visited: Set[str] = set()

        def collect_from_type(param_type: Any) -> None:
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

        for _, (_, method) in self.query_map.items():
            self._collect_from_method(method, collect_from_type)

        for _, (_, method) in self.mutation_map.items():
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

    def _build_object_type(self, entity: type) -> Dict[str, Any]:
        """Build introspection OBJECT type."""
        return {
            "kind": "OBJECT",
            "name": entity.__name__,
            "description": self._get_class_description(entity),
            "fields": self._get_entity_fields(entity),
            "inputFields": None,
            "interfaces": [],
            "enumValues": None,
            "possibleTypes": None
        }

    def _build_input_type(self, kls: type) -> Dict[str, Any]:
        """Build introspection INPUT_OBJECT type."""
        return {
            "kind": "INPUT_OBJECT",
            "name": kls.__name__,
            "description": self._get_class_description(kls),
            "fields": None,
            "inputFields": self._get_input_fields(kls),
            "interfaces": None,
            "enumValues": None,
            "possibleTypes": None
        }

    def _get_entity_fields(self, entity: type) -> List[Dict]:
        """Get introspection fields for an entity."""
        fields = []

        try:
            type_hints = get_type_hints(entity)
        except Exception:
            type_hints = {}

        # Get entity config for relationship filtering
        entity_cfg = None
        for cfg in self.er_diagram.configs:
            if cfg.kls == entity:
                entity_cfg = cfg
                break

        # Process scalar fields
        for field_name, field_type in type_hints.items():
            if field_name.startswith('__'):
                continue

            # Skip relationship fields
            if entity_cfg and self._is_relationship_field(entity_cfg, field_name):
                continue

            type_def = self._build_graphql_type(field_type)
            description = self._get_field_description(entity, field_name)

            fields.append({
                "name": field_name,
                "description": description,
                "args": [],
                "type": type_def,
                "isDeprecated": False,
                "deprecationReason": None
            })

        # Process relationships
        if entity_cfg:
            for rel in entity_cfg.relationships:
                if isinstance(rel, Relationship):
                    if not hasattr(rel, 'default_field_name') or not rel.default_field_name:
                        continue

                    field_name = rel.default_field_name
                    type_def = self._build_graphql_type(rel.target_kls)

                    fields.append({
                        "name": field_name,
                        "description": None,
                        "args": [],
                        "type": type_def,
                        "isDeprecated": False,
                        "deprecationReason": None
                    })

        return fields

    def _is_relationship_field(self, entity_cfg, field_name: str) -> bool:
        """Check if field is a relationship field."""
        for rel in entity_cfg.relationships:
            if isinstance(rel, Relationship):
                if hasattr(rel, 'default_field_name') and rel.default_field_name == field_name:
                    return True
        return False

    def _get_input_fields(self, kls: type) -> List[Dict]:
        """Get introspection inputFields for an input type."""
        fields = []

        try:
            type_hints = get_type_hints(kls)
        except Exception:
            type_hints = {}

        for field_name, field_type in type_hints.items():
            if field_name.startswith('__'):
                continue

            type_def = self._build_input_graphql_type(field_type)
            description = self._get_field_description(kls, field_name)

            fields.append({
                "name": field_name,
                "description": description,
                "type": type_def,
                "defaultValue": None
            })

        return fields

    def _get_query_fields(self) -> List[Dict]:
        """Get introspection fields for Query type."""
        return self._get_operation_fields(self.query_map, "Query")

    def _get_mutation_fields(self) -> List[Dict]:
        """Get introspection fields for Mutation type."""
        return self._get_operation_fields(self.mutation_map, "Mutation")

    def _format_default_value(self, default_value: Any) -> str:
        """Format a Python default value as a GraphQL literal string.

        Handles:
        - Enum values: UserRole.USER -> "USER"
        - Strings: "hello" -> "\"hello\""
        - Numbers: 42 -> "42"
        - Booleans: True -> "true"
        - None: None -> "null"
        """
        if default_value is None:
            return "null"

        # Handle enum values - return just the member name
        if isinstance(default_value, Enum):
            return default_value.name

        # Handle strings - need to be quoted
        if isinstance(default_value, str):
            return f'"{default_value}"'

        # Handle booleans - lowercase
        if isinstance(default_value, bool):
            return "true" if default_value else "false"

        # Handle numbers
        if isinstance(default_value, (int, float)):
            return str(default_value)

        # Fallback to string representation
        return str(default_value)

    def _get_operation_fields(self, operation_map: Dict, operation_type: str) -> List[Dict]:
        """Get introspection fields for Query or Mutation type."""
        fields = []

        for field_name, (entity, method) in operation_map.items():
            sig = inspect.signature(method)

            # Build args
            args = []
            for param_name, param in sig.parameters.items():
                if param_name in ('self', 'cls'):
                    continue

                param_type_def = None
                if param.annotation != inspect.Parameter.empty:
                    param_type_def = self._build_input_graphql_type(param.annotation)

                if param_type_def is None:
                    param_type_def = {"kind": "SCALAR", "name": "String", "ofType": None}

                has_default = param.default != inspect.Parameter.empty

                args.append({
                    "name": param_name,
                    "description": None,
                    "type": param_type_def,
                    "defaultValue": None if not has_default else self._format_default_value(param.default)
                })

            # Build return type
            return_type_def = self._build_return_type(sig.return_annotation, entity)

            fields.append({
                "name": field_name,
                "description": f"{operation_type} for {field_name}",
                "args": args,
                "type": return_type_def,
                "isDeprecated": False,
                "deprecationReason": None
            })

        return fields

    def _build_return_type(self, return_type: type, entity: type) -> Dict[str, Any]:
        """Build return type for operation fields."""
        if return_type == inspect.Parameter.empty:
            return {"kind": "SCALAR", "name": "String", "ofType": None}

        # Handle scalar types (bool, int, str, float, etc.)
        if return_type is bool:
            return {"kind": "SCALAR", "name": "Boolean", "ofType": None}
        elif return_type is int:
            return {"kind": "SCALAR", "name": "Int", "ofType": None}
        elif return_type is float:
            return {"kind": "SCALAR", "name": "Float", "ofType": None}
        elif return_type is str:
            return {"kind": "SCALAR", "name": "String", "ofType": None}

        return_type_str = str(return_type)

        # Handle list types
        if "list" in return_type_str.lower():
            return {
                "kind": "LIST",
                "name": None,
                "description": None,
                "ofType": {
                    "kind": "OBJECT",
                    "name": entity.__name__ if hasattr(entity, '__name__') else "String",
                    "ofType": None
                }
            }

        # Handle entity/object types
        if hasattr(entity, '__name__'):
            return {
                "kind": "OBJECT",
                "name": entity.__name__,
                "description": None,
                "ofType": None
            }

        return {"kind": "SCALAR", "name": "String", "ofType": None}

    def _build_graphql_type(self, field_type: Any) -> Dict[str, Any]:
        """Build GraphQL type definition for output types."""
        core_types = get_core_types(field_type)
        if not core_types:
            return {"kind": "SCALAR", "name": "String", "description": None, "ofType": None}

        core_type = core_types[0]

        if is_list_type(field_type):
            if safe_issubclass(core_type, BaseModel):
                return {
                    "kind": "LIST",
                    "name": None,
                    "description": None,
                    "ofType": {
                        "kind": "OBJECT",
                        "name": core_type.__name__,
                        "description": f"{core_type.__name__} entity",
                        "ofType": None
                    }
                }
            # Check if it's an enum type
            elif is_enum_type(core_type):
                return {
                    "kind": "LIST",
                    "name": None,
                    "description": None,
                    "ofType": {
                        "kind": "ENUM",
                        "name": core_type.__name__,
                        "description": None,
                        "ofType": None
                    }
                }
            else:
                scalar_name = map_scalar_type(core_type)
                return {
                    "kind": "LIST",
                    "name": None,
                    "description": None,
                    "ofType": {
                        "kind": "SCALAR",
                        "name": scalar_name,
                        "description": None,
                        "ofType": None
                    }
                }
        else:
            # Check if it's an enum type
            if is_enum_type(core_type):
                return {
                    "kind": "ENUM",
                    "name": core_type.__name__,
                    "description": None,
                    "ofType": None
                }
            elif safe_issubclass(core_type, BaseModel):
                return {
                    "kind": "OBJECT",
                    "name": core_type.__name__,
                    "description": f"{core_type.__name__} entity",
                    "ofType": None
                }
            else:
                scalar_name = map_scalar_type(core_type)
                return {
                    "kind": "SCALAR",
                    "name": scalar_name,
                    "description": None,
                    "ofType": None
                }

    def _build_input_graphql_type(self, field_type: Any) -> Dict[str, Any]:
        """Build GraphQL type definition for input types."""
        core_types = get_core_types(field_type)
        if not core_types:
            return {"kind": "SCALAR", "name": "String", "description": None, "ofType": None}

        core_type = core_types[0]

        if is_list_type(field_type):
            if safe_issubclass(core_type, BaseModel):
                return {
                    "kind": "LIST",
                    "name": None,
                    "description": None,
                    "ofType": {
                        "kind": "INPUT_OBJECT",
                        "name": core_type.__name__,
                        "description": f"{core_type.__name__} input",
                        "ofType": None
                    }
                }
            # Check if it's an enum type
            elif is_enum_type(core_type):
                return {
                    "kind": "LIST",
                    "name": None,
                    "description": None,
                    "ofType": {
                        "kind": "ENUM",
                        "name": core_type.__name__,
                        "description": None,
                        "ofType": None
                    }
                }
            else:
                scalar_name = map_scalar_type(core_type)
                return {
                    "kind": "LIST",
                    "name": None,
                    "description": None,
                    "ofType": {
                        "kind": "SCALAR",
                        "name": scalar_name,
                        "description": None,
                        "ofType": None
                    }
                }
        else:
            # Check if it's an enum type
            if is_enum_type(core_type):
                return {
                    "kind": "ENUM",
                    "name": core_type.__name__,
                    "description": None,
                    "ofType": None
                }
            elif safe_issubclass(core_type, BaseModel):
                return {
                    "kind": "INPUT_OBJECT",
                    "name": core_type.__name__,
                    "description": f"{core_type.__name__} input",
                    "ofType": None
                }
            else:
                scalar_name = map_scalar_type(core_type)
                return {
                    "kind": "SCALAR",
                    "name": scalar_name,
                    "description": None,
                    "ofType": None
                }

    def _format_arg(self, arg: ArgumentInfo) -> Dict[str, Any]:
        """Format an argument for introspection."""
        return {
            "name": arg.name,
            "description": arg.description,
            "type": {"kind": "SCALAR", "name": arg.graphql_type_name, "ofType": None},
            "defaultValue": arg.default_value
        }

    def _format_input_field(self, field_info: FieldInfo) -> Dict[str, Any]:
        """Format an input field for introspection."""
        return {
            "name": field_info.name,
            "description": field_info.description,
            "type": {"kind": "SCALAR", "name": field_info.graphql_type_name, "ofType": None},
            "defaultValue": None
        }

    def _build_type_ref(self, field_info: FieldInfo) -> Dict[str, Any]:
        """Build type reference for field."""
        if field_info.is_list:
            return {
                "kind": "LIST",
                "name": None,
                "ofType": {
                    "kind": "OBJECT",
                    "name": field_info.graphql_type_name,
                    "ofType": None
                }
            }
        elif field_info.is_optional:
            return {
                "kind": "OBJECT",
                "name": field_info.graphql_type_name,
                "ofType": None
            }
        else:
            return {
                "kind": "NON_NULL",
                "name": None,
                "ofType": {
                    "kind": "OBJECT",
                    "name": field_info.graphql_type_name,
                    "ofType": None
                }
            }

    def _get_class_description(self, kls: type) -> str:
        """Get description from class docstring."""
        doc = getattr(kls, '__doc__', None)
        if doc:
            doc = doc.strip()
            if doc:
                return doc
        return f"{kls.__name__} entity"

    def _get_field_description(self, kls: type, field_name: str) -> Optional[str]:
        """Get description from Pydantic field."""
        if not hasattr(kls, 'model_fields'):
            return None
        if field_name not in kls.model_fields:
            return None
        field = kls.model_fields[field_name]
        return getattr(field, 'description', None)


    def _build_enum_type(self, enum_class: type) -> Dict[str, Any]:
        """Build introspection ENUM type."""
        enum_values = get_enum_names(enum_class)
        return {
            "kind": "ENUM",
            "name": enum_class.__name__,
            "description": (enum_class.__doc__ or f"{enum_class.__name__} enum").strip(),
            "fields": None,
            "inputFields": None,
            "interfaces": None,
            "enumValues": [
                {"name": v, "description": None, "isDeprecated": False, "deprecationReason": None}
                for v in enum_values
            ],
            "possibleTypes": None
        }

    def _collect_all_enum_types(self) -> List[type]:
        """Collect all enum types from entities, input types, and query/mutation maps."""
        enums: List[type] = []
        visited: Set[str] = set()

        def collect_from_class(kls: type) -> None:
            """Collect enum types from a class's type hints."""
            try:
                type_hints = get_type_hints(kls)
            except Exception:
                return

            for field_type in type_hints.values():
                core_types_list = get_core_types(field_type)
                for ct in core_types_list:
                    if is_enum_type(ct):
                        type_name = ct.__name__
                        if type_name not in visited:
                            visited.add(type_name)
                            enums.append(ct)

        # Collect from entity types
        for entity in self._collected_types.values():
            collect_from_class(entity)

        # Collect from input types
        for input_type in self._input_types:
            collect_from_class(input_type)

        # Collect from query/mutation method parameters
        for _, (_, method) in self.query_map.items():
            try:
                sig = inspect.signature(method)
                for param_name, param in sig.parameters.items():
                    if param_name in ('self', 'cls'):
                        continue
                    if param.annotation != inspect.Parameter.empty:
                        collect_from_class(param.annotation)
            except Exception:
                pass

        for _, (_, method) in self.mutation_map.items():
            try:
                sig = inspect.signature(method)
                for param_name, param in sig.parameters.items():
                    if param_name in ('self', 'cls'):
                        continue
                    if param.annotation != inspect.Parameter.empty:
                        collect_from_class(param.annotation)
            except Exception:
                pass

        return enums
