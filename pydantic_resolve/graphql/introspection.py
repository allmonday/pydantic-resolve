"""
GraphQL introspection support.

Handles __schema, __type, and other introspection queries for GraphiQL compatibility.
"""

import inspect
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import BaseModel

from ..utils.class_util import safe_issubclass
from ..utils.types import get_core_types
from .type_mapping import map_scalar_type, is_list_type, get_graphql_type_description


# GraphQL scalar type definitions
SCALAR_TYPES = {
    "Int": {
        "kind": "SCALAR",
        "name": "Int",
        "description": "The `Int` scalar type represents non-fractional signed whole numeric values.",
        "fields": None,
        "inputFields": None,
        "interfaces": None,
        "enumValues": None,
        "possibleTypes": None
    },
    "Float": {
        "kind": "SCALAR",
        "name": "Float",
        "description": "The `Float` scalar type represents signed double-precision fractional values.",
        "fields": None,
        "inputFields": None,
        "interfaces": None,
        "enumValues": None,
        "possibleTypes": None
    },
    "String": {
        "kind": "SCALAR",
        "name": "String",
        "description": "The `String` scalar type represents textual data.",
        "fields": None,
        "inputFields": None,
        "interfaces": None,
        "enumValues": None,
        "possibleTypes": None
    },
    "Boolean": {
        "kind": "SCALAR",
        "name": "Boolean",
        "description": "The `Boolean` scalar type represents `true` or `false`.",
        "fields": None,
        "inputFields": None,
        "interfaces": None,
        "enumValues": None,
        "possibleTypes": None
    },
    "ID": {
        "kind": "SCALAR",
        "name": "ID",
        "description": "The `ID` scalar type represents a unique identifier.",
        "fields": None,
        "inputFields": None,
        "interfaces": None,
        "enumValues": None,
        "possibleTypes": None
    },
}


class IntrospectionHelper:
    """
    GraphQL introspection helper.

    Provides introspection support for GraphiQL and other GraphQL tools.
    """

    def __init__(
        self,
        er_diagram,
        query_map: Dict[str, Tuple[type, Callable]],
        mutation_map: Dict[str, Tuple[type, Callable]]
    ):
        """
        Args:
            er_diagram: Entity relationship diagram
            query_map: Mapping of query names to (entity, method) tuples
            mutation_map: Mapping of mutation names to (entity, method) tuples
        """
        self.er_diagram = er_diagram
        self.query_map = query_map
        self.mutation_map = mutation_map

    def is_introspection_query(self, query: str) -> bool:
        """Check if this is an introspection query."""
        query_stripped = query.strip()
        introspection_keywords = ["__schema", "__type", "__typename"]
        return any(keyword in query_stripped for keyword in introspection_keywords)

    def parse_introspection_query(self, query: str) -> Dict[str, Any]:
        """Parse introspection query and extract requested fields."""
        from graphql import parse as parse_graphql

        try:
            parse_graphql(query)

            # Simplified: check if query requests __type
            requests_type = "__type(" in query or '__type (' in query.replace('"', "'")

            return {
                "requests_schema": "__schema" in query,
                "requests_type": requests_type
            }
        except Exception:
            # Parse failed, assume both are requested
            return {
                "requests_schema": True,
                "requests_type": True
            }

    async def execute(self, query: str) -> Dict[str, Any]:
        """Execute introspection query - returns full introspection data to support GraphiQL."""
        # Parse query to determine requested content
        query_info = self.parse_introspection_query(query)

        # Build response data
        data = {}

        if query_info["requests_schema"]:
            data["__schema"] = {
                "queryType": {
                    "name": "Query",
                    "kind": "OBJECT"
                },
                "mutationType": {
                    "name": "Mutation",
                    "kind": "OBJECT"
                } if self.mutation_map else None,
                "subscriptionType": None,
                "types": self._get_introspection_types(),
                "directives": []  # Directives not supported yet
            }

        if query_info["requests_type"]:
            # Try to extract type name from query
            type_name = self._extract_type_name_from_query(query)
            if type_name:
                data["__type"] = self._get_introspection_type(type_name)

        return {
            "data": data,
            "errors": None
        }

    def _extract_type_name_from_query(self, query: str) -> Optional[str]:
        """Extract type name from query."""
        # Match __type(name: "TypeName")
        match = re.search(r'__type\s*\(\s*name\s*:\s*["\']([^"\']+)["\']', query)
        if match:
            return match.group(1)

        # Match __type(name: 'TypeName')
        match = re.search(r"__type\s*\(\s*name\s*:\s*'([^']+)'", query)
        if match:
            return match.group(1)

        return None

    def _get_introspection_type(self, type_name: str) -> Optional[Dict[str, Any]]:
        """Get introspection info for a specific type."""
        # Check scalar types
        if type_name in SCALAR_TYPES:
            return SCALAR_TYPES[type_name]

        # Collect all types (including nested Pydantic types)
        collected_types = {}
        for entity_cfg in self.er_diagram.configs:
            collected_types[entity_cfg.kls.__name__] = entity_cfg.kls

        # Collect nested types
        additional_types = self._collect_nested_pydantic_types(list(collected_types.values()))
        for name, cls in additional_types.items():
            if name not in collected_types:
                collected_types[name] = cls

        # Check entity types
        if type_name in collected_types:
            entity = collected_types[type_name]
            description = self._get_class_description(entity)
            return {
                "kind": "OBJECT",
                "name": type_name,
                "description": description,
                "fields": self._get_introspection_fields(entity),
                "inputFields": None,
                "interfaces": [],  # OBJECT types must have interfaces as array
                "enumValues": None,
                "possibleTypes": None
            }

        # Check Query type
        if type_name == "Query":
            return {
                "kind": "OBJECT",
                "name": "Query",
                "description": "Root query type",
                "fields": self._get_introspection_query_fields(),
                "inputFields": None,
                "interfaces": [],
                "enumValues": None,
                "possibleTypes": None
            }

        # Check Mutation type
        if type_name == "Mutation":
            return {
                "kind": "OBJECT",
                "name": "Mutation",
                "description": "Root mutation type",
                "fields": self._get_introspection_mutation_fields(),
                "inputFields": None,
                "interfaces": [],
                "enumValues": None,
                "possibleTypes": None
            }

        return None

    def _get_introspection_types(self) -> List[Dict]:
        """Get introspection type list."""
        types = []

        # Add scalar types
        types.extend([SCALAR_TYPES[name] for name in ["Int", "Float", "String", "Boolean", "ID"]])

        # Collect all entity types (including entities in ERD and nested Pydantic models in fields)
        collected_types = {}

        # First collect entities from ERD
        for entity_cfg in self.er_diagram.configs:
            collected_types[entity_cfg.kls.__name__] = entity_cfg.kls

        # Recursively collect all Pydantic BaseModel types referenced in fields
        additional_types = self._collect_nested_pydantic_types(list(collected_types.values()))
        for type_name, type_class in additional_types.items():
            if type_name not in collected_types:
                collected_types[type_name] = type_class

        # Generate introspection for all collected types
        for type_name, entity in collected_types.items():
            description = self._get_class_description(entity)
            entity_type = {
                "kind": "OBJECT",
                "name": entity.__name__,
                "description": description,
                "fields": self._get_introspection_fields(entity),
                "inputFields": None,
                "interfaces": [],
                "enumValues": None,
                "possibleTypes": None
            }
            types.append(entity_type)

        # Collect and add all Input Types
        input_types = self._collect_input_types_for_introspection()
        for input_type in input_types:
            description = self._get_class_description(input_type)
            input_type_def = {
                "kind": "INPUT_OBJECT",
                "name": input_type.__name__,
                "description": description,
                "fields": None,
                "inputFields": self._get_introspection_input_fields(input_type),
                "interfaces": None,
                "enumValues": None,
                "possibleTypes": None
            }
            types.append(input_type_def)

        # Add Query type
        types.append({
            "kind": "OBJECT",
            "name": "Query",
            "description": "Root query type",
            "fields": self._get_introspection_query_fields(),
            "inputFields": None,
            "interfaces": [],
            "enumValues": None,
            "possibleTypes": None
        })

        # Add Mutation type (if there are mutations)
        if self.mutation_map:
            types.append({
                "kind": "OBJECT",
                "name": "Mutation",
                "description": "Root mutation type",
                "fields": self._get_introspection_mutation_fields(),
                "inputFields": None,
                "interfaces": [],
                "enumValues": None,
                "possibleTypes": None
            })

        return types

    def _collect_input_types_for_introspection(self) -> set:
        """
        Collect all BaseModel types from method parameters as Input Types (for Introspection).

        Returns:
            Set of all BaseModel types that need input definitions
        """
        input_types = set()
        visited = set()

        def collect_from_type(param_type):
            """Recursively collect BaseModel types."""
            core_types = get_core_types(param_type)

            for core_type in core_types:
                if safe_issubclass(core_type, BaseModel):
                    type_name = core_type.__name__
                    if type_name not in visited:
                        visited.add(type_name)
                        input_types.add(core_type)

                        # Recursively collect nested BaseModel types
                        if hasattr(core_type, '__annotations__'):
                            for field_type in core_type.__annotations__.values():
                                collect_from_type(field_type)

        # Traverse all @query methods
        for _, (entity, method) in self.query_map.items():
            try:
                sig = inspect.signature(method)
                for param_name, param in sig.parameters.items():
                    if param_name in ('self', 'cls'):
                        continue
                    if param.annotation != inspect.Parameter.empty:
                        collect_from_type(param.annotation)
            except Exception:
                pass

        # Traverse all @mutation methods
        for _, (entity, method) in self.mutation_map.items():
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

    def _get_introspection_input_fields(self, input_type: type) -> List[Dict]:
        """
        Get introspection fields for an Input Type.

        Args:
            input_type: Pydantic BaseModel class

        Returns:
            List of field info dictionaries
        """
        fields = []

        if hasattr(input_type, '__annotations__'):
            for field_name, field_type in input_type.__annotations__.items():
                if field_name.startswith('__'):
                    continue

                # Build field type info
                type_def = self._build_input_graphql_type(field_type)

                # Get field description
                description = self._get_field_description(input_type, field_name)

                fields.append({
                    "name": field_name,
                    "description": description,
                    "type": type_def,
                    "defaultValue": None
                })

        return fields

    def _build_input_graphql_type(self, field_type: Any) -> Dict[str, Any]:
        """
        Map Python type to GraphQL Input type definition (for Introspection).

        Args:
            field_type: Python type

        Returns:
            GraphQL type definition dictionary
        """
        core_types = get_core_types(field_type)
        if not core_types:
            return {
                "kind": "SCALAR",
                "name": "String",
                "description": None,
                "ofType": None
            }

        core_type = core_types[0]

        # Check if it's list[T]
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
            if safe_issubclass(core_type, BaseModel):
                return {
                    "kind": "INPUT_OBJECT",
                    "name": core_type.__name__,
                    "description": f"{core_type.__name__} input",
                    "ofType": None
                }
            else:
                scalar_name = map_scalar_type(core_type)
                desc = get_graphql_type_description(scalar_name)
                return {
                    "kind": "SCALAR",
                    "name": scalar_name,
                    "description": desc,
                    "ofType": None
                }

    def _is_pydantic_basemodel(self, type_hint: Any) -> bool:
        """
        Check if type is Pydantic BaseModel

        Args:
            type_hint: Type hint

        Returns:
            Whether it's Pydantic BaseModel
        """
        core_types = get_core_types(type_hint)
        return any(safe_issubclass(t, BaseModel) for t in core_types)

    def _extract_list_element_type(self, field_type: Any) -> Optional[type]:
        """
        Extract element type T from list[T]

        Args:
            field_type: Field type (possibly list[T])

        Returns:
            Element type, or None if not a list
        """
        from typing import get_args, get_origin

        origin = get_origin(field_type)
        if origin is list:
            args = get_args(field_type)
            if args:
                return args[0]
        return None

    def _collect_nested_pydantic_types(self, entities: list, visited: Optional[set] = None) -> Dict[str, type]:
        """
        Recursively collect all Pydantic BaseModel types referenced in entity fields

        Args:
            entities: List of entities to scan
            visited: Set of already visited type names (to avoid circular references)

        Returns:
            Dictionary mapping type names to type classes
        """
        if visited is None:
            visited = set()

        collected = {}

        for entity in entities:
            type_name = entity.__name__
            if type_name in visited:
                continue
            visited.add(type_name)

            # Scan all fields of the entity
            if hasattr(entity, '__annotations__'):
                for field_name, field_type in entity.__annotations__.items():
                    if field_name.startswith('__'):
                        continue

                    core_types = get_core_types(field_type)
                    for core_type in core_types:
                        if safe_issubclass(core_type, BaseModel):
                            if core_type.__name__ not in collected and core_type.__name__ not in visited:
                                collected[core_type.__name__] = core_type

        # Recursively collect nested types of newly discovered types
        if collected:
            nested_types = self._collect_nested_pydantic_types(list(collected.values()), visited)
            collected.update(nested_types)

        return collected

    def _get_field_description(self, entity: type, field_name: str) -> Optional[str]:
        """
        Get field description information

        Prefer Pydantic Field's description attribute

        Args:
            entity: Entity class
            field_name: Field name

        Returns:
            Field description string, or None if not found
        """
        if not hasattr(entity, 'model_fields'):
            return None

        if field_name not in entity.model_fields:
            return None

        field = entity.model_fields[field_name]
        return getattr(field, 'description', None)

    def _get_class_description(self, entity: type) -> str:
        """
        Get class description information

        Prefer class's __doc__, otherwise use default format

        Args:
            entity: Entity class

        Returns:
            Class description string
        """
        doc = getattr(entity, '__doc__', None)

        if doc:
            doc = doc.strip()
            if doc:
                return doc

        return f"{entity.__name__} entity"

    def _get_introspection_fields(self, entity: type) -> List[Dict]:
        """Get introspection fields for entity"""
        from ..utils.er_diagram import Relationship, MultipleRelationship

        fields = []

        # 1. Process scalar fields (from __annotations__)
        if hasattr(entity, '__annotations__'):
            for field_name, field_type in entity.__annotations__.items():
                if field_name.startswith('__'):
                    continue

                # Skip relationship fields (handled by relationship section)
                is_relationship_field = False
                entity_cfg = None
                for cfg in self.er_diagram.configs:
                    if cfg.kls == entity:
                        entity_cfg = cfg
                        break
                if entity_cfg:
                    for rel in entity_cfg.relationships:
                        if isinstance(rel, Relationship):
                            if hasattr(rel, 'default_field_name') and rel.default_field_name == field_name:
                                is_relationship_field = True
                                break
                        elif isinstance(rel, MultipleRelationship):
                            for link in rel.links:
                                if hasattr(link, 'default_field_name') and link.default_field_name == field_name:
                                    is_relationship_field = True
                                    break
                            if is_relationship_field:
                                break
                if is_relationship_field:
                    continue

                # Build field type information
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

        # 2. Process relationships (from __relationships__)
        entity_cfg = None
        for cfg in self.er_diagram.configs:
            if cfg.kls == entity:
                entity_cfg = cfg
                break

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

                elif isinstance(rel, MultipleRelationship):
                    for link in rel.links:
                        if not hasattr(link, 'default_field_name') or not link.default_field_name:
                            continue

                        field_name = link.default_field_name
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

    def _build_graphql_type(self, field_type: Any) -> Dict[str, Any]:
        """
        Map Python type to GraphQL type definition

        Args:
            field_type: Python type (can be list[T], Optional[T], T, etc.)

        Returns:
            GraphQL type definition dictionary
        """
        core_types = get_core_types(field_type)
        if not core_types:
            return {
                "kind": "SCALAR",
                "name": "String",
                "description": None,
                "ofType": None
            }

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
            if safe_issubclass(core_type, BaseModel):
                return {
                    "kind": "OBJECT",
                    "name": core_type.__name__,
                    "description": f"{core_type.__name__} entity",
                    "ofType": None
                }
            else:
                scalar_name = map_scalar_type(core_type)
                desc = get_graphql_type_description(scalar_name)
                if "dict" in str(core_type).lower():
                    scalar_name = "String"
                    desc = "JSON string representation"

                return {
                    "kind": "SCALAR",
                    "name": scalar_name,
                    "description": desc,
                    "ofType": None
                }

    def _get_introspection_operation_fields(self, operation_map: Dict[str, Tuple[type, Callable]], operation_type: str) -> List[Dict]:
        """
        Get introspection fields for Query or Mutation type.

        Args:
            operation_map: Either self.query_map or self.mutation_map
            operation_type: "Query" or "Mutation" for description
        """
        fields = []

        for field_name, (entity, method) in operation_map.items():
            sig = inspect.signature(method)

            # Build parameter list
            args = []
            for param_name, param in sig.parameters.items():
                if param_name in ('self', 'cls'):
                    continue

                param_type_def = None

                if param.annotation != inspect.Parameter.empty:
                    param_type_def = self._build_input_graphql_type(param.annotation)

                if param_type_def is None:
                    param_type_def = {
                        "kind": "SCALAR",
                        "name": "String",
                        "ofType": None
                    }

                has_default = param.default != inspect.Parameter.empty

                args.append({
                    "name": param_name,
                    "description": None,
                    "type": param_type_def,
                    "defaultValue": None if not has_default else str(param.default)
                })

            # Determine return type
            return_type_str = str(sig.return_annotation) if sig.return_annotation != sig.empty else "String"
            return_kind = "SCALAR"
            return_name = "String"
            of_type = None

            if "list" in return_type_str.lower():
                return_kind = "LIST"
                return_name = None
                if hasattr(entity, '__name__'):
                    of_type = {
                        "kind": "OBJECT",
                        "name": entity.__name__,
                        "ofType": None
                    }
                else:
                    of_type = {
                        "kind": "SCALAR",
                        "name": "String",
                        "ofType": None
                    }
            elif hasattr(entity, '__name__'):
                return_name = entity.__name__
                return_kind = "OBJECT"

            type_def = {
                "kind": return_kind,
                "name": return_name,
                "description": None,
                "ofType": of_type
            }

            # Add other required fields based on type kind
            if return_kind == "SCALAR":
                type_def["fields"] = None
                type_def["inputFields"] = None
                type_def["interfaces"] = None
                type_def["enumValues"] = None
                type_def["possibleTypes"] = None
            elif return_kind == "OBJECT":
                type_def["fields"] = self._get_introspection_fields(entity)
                type_def["inputFields"] = None
                type_def["interfaces"] = None
                type_def["enumValues"] = None
                type_def["possibleTypes"] = None
            elif return_kind == "LIST":
                type_def["fields"] = None
                type_def["inputFields"] = None
                type_def["interfaces"] = None
                type_def["enumValues"] = None
                type_def["possibleTypes"] = None

            fields.append({
                "name": field_name,
                "description": f"{operation_type} for {field_name}",
                "args": args,
                "type": type_def,
                "isDeprecated": False,
                "deprecationReason": None
            })

        return fields

    def _get_introspection_query_fields(self) -> List[Dict]:
        """Get introspection fields for Query type"""
        return self._get_introspection_operation_fields(self.query_map, "Query")

    def _get_introspection_mutation_fields(self) -> List[Dict]:
        """Get introspection fields for Mutation type"""
        return self._get_introspection_operation_fields(self.mutation_map, "Mutation")
