"""
GraphQL handler - coordinates all components and provides FastAPI integration.
"""

import asyncio
import inspect
import logging
import os
import re
from typing import Any, Callable, Dict, List, Tuple, Optional
from typing import get_origin
from pydantic import BaseModel
from ..utils.class_util import safe_issubclass
from ..utils.types import get_core_types
from .type_mapping import map_scalar_type, is_list_type, get_graphql_type_description

from ..resolver import Resolver
from ..utils.er_diagram import ErDiagram
from .query_parser import QueryParser
from .schema_builder import SchemaBuilder
from .response_builder import ResponseBuilder
from .exceptions import GraphQLError

logger = logging.getLogger(__name__)

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


class GraphQLHandler:
    """
    GraphQL query handler

    Coordinates all components: parses queries, executes @query methods,
    builds response models, and resolves relationships.
    """

    def __init__(
        self,
        er_diagram: ErDiagram,
        resolver_class: type[Resolver] = Resolver,
        enable_from_attribute_in_type_adapter: bool = False
    ):
        """
        Args:
            er_diagram: Entity relationship diagram
            resolver_class: Custom Resolver class (optional)
            enable_from_attribute_in_type_adapter: Enable Pydantic from_attributes mode for type adapter validation.
                Allows loaders to return Pydantic instances instead of dictionaries.
        """
        self.er_diagram = er_diagram
        self.parser = QueryParser()
        self.builder = ResponseBuilder(er_diagram)
        self.schema_builder = SchemaBuilder(er_diagram)
        self.resolver_class = resolver_class
        self.enable_from_attribute_in_type_adapter = enable_from_attribute_in_type_adapter

        # Build query method map: { 'users': (UserEntity, UserEntity.get_all) }
        self.query_map = self._build_query_map()

        # Build mutation method map: { 'createUser': (UserEntity, UserEntity.create_user) }
        self.mutation_map = self._build_mutation_map()

    def _build_query_map(self) -> Dict[str, Tuple[type, Callable]]:
        """
        Scan all entities and build query name to method mapping.

        Returns:
            Dictionary mapping query names to (return entity class, method) tuples
        """
        query_map = {}
        for entity_cfg in self.er_diagram.configs:
            methods = self.schema_builder._extract_query_methods(entity_cfg.kls)
            for method_info in methods:
                query_name = method_info['name']
                # Extract return entity class from method's return type annotation
                return_entity = self._extract_return_entity(method_info['method'])
                query_map[query_name] = (return_entity, method_info['method'])
        return query_map

    def _build_mutation_map(self) -> Dict[str, Tuple[type, Callable]]:
        """
        Scan all entities and build mutation name to method mapping.

        Returns:
            Dictionary mapping mutation names to (return entity class, method) tuples
        """
        mutation_map = {}
        for entity_cfg in self.er_diagram.configs:
            methods = self.schema_builder._extract_mutation_methods(entity_cfg.kls)
            for method_info in methods:
                mutation_name = method_info['name']
                # Extract return entity class from method's return type annotation
                return_entity = self._extract_return_entity(method_info['method'])
                mutation_map[mutation_name] = (return_entity, method_info['method'])
        return mutation_map

    def _extract_return_entity(self, method: Callable) -> Optional[type]:
        """
        Extract the return entity class from method's return type annotation.

        Handles:
        - List[Entity] -> Entity (first element)
        - Optional[List[Entity]] -> Entity (first element)
        - Optional[Entity] -> Entity
        - Entity -> Entity
        - Forward references are resolved using ERD lookup

        Args:
            method: @query decorated method

        Returns:
            Entity class if found, None otherwise
        """
        import types
        from typing import ForwardRef, get_origin, get_args, Union

        sig = inspect.signature(method)
        return_annotation = sig.return_annotation

        if return_annotation == inspect.Parameter.empty:
            return None

        origin = get_origin(return_annotation)

        # Unwrap Optional[List[T]] -> List[T] -> T
        if origin is list:
            args = get_args(return_annotation)
            if args:
                return_annotation = args[0]
                origin = get_origin(return_annotation)
        # Handle Optional[Entity] (Union[Entity, None]) - extract Entity
        elif origin is Union or (hasattr(types, 'UnionType') and isinstance(return_annotation, types.UnionType)):
            args = get_args(return_annotation)
            non_none_args = [a for a in args if a is not type(None)]
            if len(non_none_args) == 1:
                return_annotation = non_none_args[0]
                # Check if it's Optional[List[T]]
                if get_origin(return_annotation) is list:
                    args = get_args(return_annotation)
                    if args:
                        return_annotation = args[0]

        # Handle ForwardRef
        if isinstance(return_annotation, ForwardRef):
            type_name = return_annotation.__forward_arg__
            # Look up in ERD
            for cfg in self.er_diagram.configs:
                if cfg.kls.__name__ == type_name:
                    return cfg.kls

        # Handle string annotation (from __future__ import annotations)
        if isinstance(return_annotation, str):
            # Look up in ERD
            for cfg in self.er_diagram.configs:
                if cfg.kls.__name__ == return_annotation:
                    return cfg.kls

        # Handle direct class reference
        if isinstance(return_annotation, type):
            return return_annotation

        return None

    async def execute(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query or mutation.

        Args:
            query: GraphQL query string
            variables: Query variables
            operation_name: Operation name

        Returns:
            GraphQL response format: {"data": {...}, "errors": [...]}
        """
        logger.debug(f"Executing GraphQL: {query[:100]}...")
        try:
            # Check for introspection query
            is_introspection = self._is_introspection_query(query)

            if is_introspection:
                logger.debug("Processing introspection query")
                # Execute introspection query using graphql-core
                return await self._execute_introspection(query)
            else:
                # Detect operation type (query or mutation)
                operation_type = self._detect_operation_type(query)

                if operation_type == 'mutation':
                    logger.debug("Processing mutation")
                    return await self._execute_custom_mutation(query)
                else:
                    logger.debug("Processing query")
                    return await self._execute_custom_query(query)

        except GraphQLError as e:
            logger.warning(f"GraphQL error: {e.message}")
            return {
                "data": None,
                "errors": [e.to_dict()]
            }
        except Exception as e:
            logger.exception("Unexpected error during GraphQL query execution")
            return {
                "data": None,
                "errors": [
                    {
                        "message": str(e),
                        "extensions": {"code": type(e).__name__}
                    }
                ]
            }

    def _is_introspection_query(self, query: str) -> bool:
        """Check if this is an introspection query."""
        query_stripped = query.strip()
        # Check for introspection keywords: __schema, __type, __typename
        introspection_keywords = ["__schema", "__type", "__typename"]
        return any(keyword in query_stripped for keyword in introspection_keywords)

    def _detect_operation_type(self, query: str) -> str:
        """
        Detect operation type (query or mutation).

        Args:
            query: GraphQL query string

        Returns:
            'query' or 'mutation'
        """
        query_stripped = query.strip()

        # Check for explicit 'mutation' keyword
        if query_stripped.startswith('mutation'):
            return 'mutation'

        # Check if root field is in mutation_map (for implicit mutations without 'mutation' keyword)
        for mutation_name in self.mutation_map.keys():
            if mutation_name in query_stripped:
                return 'mutation'

        return 'query'

    def _parse_introspection_query(self, query: str) -> Dict[str, Any]:
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

    async def _execute_introspection(self, query: str) -> Dict[str, Any]:
        """Execute introspection query - returns full introspection data to support GraphiQL."""

        # Parse query to determine requested content
        query_info = self._parse_introspection_query(query)

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
            # Get class description
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
                "interfaces": [],  # OBJECT types must have interfaces as array
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

    def _get_introspection_types(self):
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
            # Get class description
            description = self._get_class_description(entity)
            entity_type = {
                "kind": "OBJECT",
                "name": entity.__name__,
                "description": description,
                "fields": self._get_introspection_fields(entity),
                "inputFields": None,
                "interfaces": [],  # OBJECT types must have interfaces as array
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
            "interfaces": [],  # OBJECT types must have interfaces as array
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
        # Use get_core_types to extract core types, handling Optional[T], list[T], Annotated[T, ...] wrappers
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
        from typing import get_args

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

                    # Use get_core_types to handle all wrapper types (Optional, list, Annotated, etc.)
                    # Then check if each core type is Pydantic BaseModel
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
        # Check if it's a Pydantic model with model_fields
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
        # Get class docstring
        doc = getattr(entity, '__doc__', None)

        # Clean docstring (remove leading/trailing whitespace)
        if doc:
            doc = doc.strip()
            if doc:
                return doc

        # If no docstring, use default format
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
                            # 检查 links 中的 default_field_name
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
                # Get field description
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
                    # Only relationships with default_field_name are exposed to GraphQL
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
                    # Process MultipleRelationship links
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
        # Use get_core_types to handle all wrapper types
        core_types = get_core_types(field_type)
        if not core_types:
            # Cannot determine type, default to String
            return {
                "kind": "SCALAR",
                "name": "String",
                "description": None,
                "ofType": None
            }

        # Get core type
        core_type = core_types[0]

        # Check if it's list[T]
        if is_list_type(field_type):
            # list[T] -> LIST type
            if safe_issubclass(core_type, BaseModel):
                # list[Entity] -> LIST -> OBJECT
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
                # list[Scalar] -> LIST -> SCALAR
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
            # T (non-list)
            if safe_issubclass(core_type, BaseModel):
                # Entity -> OBJECT
                return {
                    "kind": "OBJECT",
                    "name": core_type.__name__,
                    "description": f"{core_type.__name__} entity",
                    "ofType": None
                }
            else:
                # Scalar -> SCALAR
                scalar_name = map_scalar_type(core_type)
                # Add special description
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

                # Determine parameter type
                param_type_def = None

                # Try to get type from type annotation
                if param.annotation != inspect.Parameter.empty:
                    param_type_def = self._build_input_graphql_type(param.annotation)

                # If type cannot be determined, use default String
                if param_type_def is None:
                    param_type_def = {
                        "kind": "SCALAR",
                        "name": "String",
                        "ofType": None
                    }

                # Check if it has default value
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

    def _get_introspection_query_fields(self):
        """Get introspection fields for Query type"""
        return self._get_introspection_operation_fields(self.query_map, "Query")

    def _get_introspection_mutation_fields(self):
        """Get introspection fields for Mutation type"""
        return self._get_introspection_operation_fields(self.mutation_map, "Mutation")

    async def _execute_custom_query(
        self,
        query: str,
    ) -> Dict[str, Any]:
        """
        Execute custom query with optimized two-phase execution:
        - Phase 1 (Serial): Query method execution, model building, data transformation
        - Phase 2 (Concurrent): Parallel execution of all root query Resolvers
        """
        logger.info("Starting custom query execution with concurrent optimization")

        # 1. Parse query
        parsed = self.parser.parse(query)
        logger.debug(f"Query parsed: {len(parsed.field_tree)} root fields found")

        # 2. Initialize results
        errors = []
        data = {}

        # ===== Phase 1: Serial Preparation =====
        logger.info("[Phase 1] Starting serial preparation phase")

        preparation_results = {}  # query_name -> (typed_data, is_list)

        for root_query_name, root_field_selection in parsed.field_tree.items():
            try:
                # Check if query exists
                if root_query_name not in self.query_map:
                    errors.append({
                        "message": f"Unknown query: {root_query_name}",
                        "extensions": {"code": "UNKNOWN_QUERY"}
                    })
                    logger.warning(f"[Phase 1] Unknown query: {root_query_name}")
                    continue

                entity, query_method = self.query_map[root_query_name]

                # Prepare query resolution
                typed_data, error_msg, error_dict = await self._prepare_query_resolution(
                    root_query_name=root_query_name,
                    root_field_selection=root_field_selection,
                    entity=entity,
                    query_method=query_method
                )

                if error_dict:
                    errors.append(error_dict)
                else:
                    # Store for Phase 2
                    is_list = isinstance(typed_data, list)
                    preparation_results[root_query_name] = (typed_data, is_list)

            except GraphQLError as e:
                errors.append(e.to_dict())
            except Exception as e:
                logger.exception(f"Unexpected error in Phase 1 for {root_query_name}")
                errors.append({
                    "message": str(e),
                    "extensions": {"code": type(e).__name__}
                })

        logger.info(f"[Phase 1] Completed: {len(preparation_results)} queries prepared, {len(errors)} errors")

        # ===== Phase 2: Concurrent Resolution =====
        logger.info("[Phase 2] Starting concurrent resolution phase")

        if preparation_results:
            # Build resolution tasks
            resolution_tasks = [
                (name, data, is_list)
                for name, (data, is_list) in preparation_results.items()
            ]

            # Execute all resolutions concurrently
            resolution_map = await self._execute_concurrent_resolutions(resolution_tasks)

            # Collect results and errors
            for query_name, (result_data, error_dict) in resolution_map.items():
                if error_dict:
                    errors.append(error_dict)
                else:
                    data[query_name] = result_data

        logger.info(f"[Phase 2] Completed: {len(data)} queries resolved successfully")

        # 3. Format response
        response = {
            "data": data if data else None,
            "errors": errors if errors else None
        }

        logger.info(f"Query execution complete: {len(data) if data else 0} successful, {len(errors) if errors else 0} errors")
        return response

    async def _execute_custom_mutation(
        self,
        query: str,
    ) -> Dict[str, Any]:
        """
        Execute custom mutation with two-phase execution:
        - Phase 1 (Serial): Mutation method execution, model building, data transformation
        - Phase 2 (Serial): Execute Resolver to resolve related data (each mutation executed sequentially)
        """
        logger.info("Starting custom mutation execution")

        # 1. Parse mutation
        parsed = self.parser.parse(query)
        logger.debug(f"Mutation parsed: {len(parsed.field_tree)} root fields found")

        # 2. Initialize results
        errors = []
        data = {}

        # ===== Phase 1 + Phase 2: Serial execution of each mutation =====
        logger.info("Starting serial mutation execution with two-phase resolution")

        for root_mutation_name, root_field_selection in parsed.field_tree.items():
            try:
                # Check if mutation exists
                if root_mutation_name not in self.mutation_map:
                    errors.append({
                        "message": f"Unknown mutation: {root_mutation_name}",
                        "extensions": {"code": "UNKNOWN_MUTATION"}
                    })
                    logger.warning(f"Unknown mutation: {root_mutation_name}")
                    continue

                entity, mutation_method = self.mutation_map[root_mutation_name]

                # === Phase 1: Execute mutation method ===
                args = root_field_selection.arguments or {}
                root_data = await self._execute_method(mutation_method, args, "mutation")
                logger.debug(f"Mutation method executed: {root_mutation_name}")

                # === Phase 1: Build response model ===
                response_model = self.builder.build_response_model(
                    entity=entity,
                    field_selection=root_field_selection
                )
                logger.debug(f"Response model built: {root_mutation_name}")

                # === Phase 1: Transform to response model ===
                if isinstance(root_data, list):
                    typed_data = [
                        response_model.model_validate(
                            d.model_dump() if hasattr(d, 'model_dump') else d
                        )
                        for d in root_data
                    ]
                elif root_data is not None:
                    typed_data = response_model.model_validate(
                        root_data.model_dump() if hasattr(root_data, 'model_dump') else root_data
                    )
                else:
                    typed_data = None

                logger.debug(f"Data transformed: {root_mutation_name}")

                # === Phase 2: Resolve related data ===
                if typed_data is not None:
                    resolver = self.resolver_class(enable_from_attribute_in_type_adapter=self.enable_from_attribute_in_type_adapter)

                    if isinstance(typed_data, list):
                        resolved = await resolver.resolve(typed_data)
                        data[root_mutation_name] = [r.model_dump(by_alias=True) for r in resolved] if resolved else []
                    else:
                        resolved = await resolver.resolve(typed_data)
                        data[root_mutation_name] = resolved.model_dump(by_alias=True) if resolved else None
                else:
                    data[root_mutation_name] = None

                logger.debug(f"Mutation resolved: {root_mutation_name}")

            except GraphQLError as e:
                errors.append(e.to_dict())
            except Exception as e:
                logger.exception(f"Unexpected error executing {root_mutation_name}")
                errors.append({
                    "message": str(e),
                    "extensions": {"code": type(e).__name__}
                })

        logger.info(f"Mutation execution complete: {len(data) if data else 0} successful, {len(errors) if errors else 0} errors")

        # 3. Format response
        response = {
            "data": data if data else None,
            "errors": errors if errors else None
        }

        return response

    async def _execute_method(
        self,
        method: Callable,
        arguments: Dict[str, Any],
        operation_type: str = "query"
    ) -> Any:
        """
        Execute @query or @mutation method

        Args:
            method: @query/@mutation decorated method (can be classmethod or regular function)
            arguments: Parameter dictionary
            operation_type: "query" or "mutation" for logging

        Returns:
            Method result
        """
        logger.debug(f"Executing {operation_type} method with arguments: {arguments}")
        try:
            # Convert arguments (handle BaseModel types)
            converted_args = self._convert_arguments(method, arguments)

            # schema_builder has extracted the underlying function (for classmethod it's __func__)
            # Call directly, passing None for first parameter (cls/self)
            return await method(None, **converted_args)
        except Exception as e:
            logger.error(f"{operation_type.capitalize()} method execution failed: {e}")
            raise GraphQLError(
                f"{operation_type.capitalize()} execution failed: {e}",
                extensions={"code": "EXECUTION_ERROR"}
            )

    def _convert_arguments(
        self,
        method: Callable,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Convert method parameters, transforming dict to corresponding Pydantic BaseModel instances

        Args:
            method: Method object
            arguments: Original parameter dictionary

        Returns:
            Converted parameter dictionary
        """
        converted = {}
        try:
            sig = inspect.signature(method)
            for param_name, param in sig.parameters.items():
                if param_name in ('self', 'cls'):
                    continue

                if param_name not in arguments:
                    continue

                value = arguments[param_name]
                param_type = param.annotation

                # If parameter type is BaseModel and value is dict, convert
                if param_type != inspect.Parameter.empty:
                    core_types = get_core_types(param_type)
                    converted_value = None
                    for core_type in core_types:
                        if safe_issubclass(core_type, BaseModel):
                            if isinstance(value, dict):
                                converted_value = self._convert_to_model(value, core_type)
                                break
                            elif isinstance(value, list):
                                list_element_type = self._extract_list_element_type(param_type)
                                if list_element_type and safe_issubclass(list_element_type, BaseModel):
                                    converted_value = [
                                        self._convert_to_model(item, list_element_type) if isinstance(item, dict) else item
                                        for item in value
                                    ]
                                break
                    if converted_value is not None:
                        converted[param_name] = converted_value
                    else:
                        converted[param_name] = value
                else:
                    converted[param_name] = value

        except Exception as e:
            logger.warning(f"Failed to convert arguments: {e}")
            return arguments

        return converted

    def _convert_to_model(self, data: dict, model_class: type) -> BaseModel:
        """
        Recursively convert dict to Pydantic BaseModel instance

        Args:
            data: Dictionary data
            model_class: Target BaseModel class

        Returns:
            BaseModel instance
        """
        # Get all field types of the model
        try:
            type_hints = model_class.__annotations__
        except Exception:
            type_hints = {}

        converted_data = {}
        for field_name, field_value in data.items():
            if field_name in type_hints:
                field_type = type_hints[field_name]
                core_types = get_core_types(field_type)

                # Check if field type is BaseModel
                is_model_field = False
                for core_type in core_types:
                    if safe_issubclass(core_type, BaseModel):
                        if isinstance(field_value, dict):
                            converted_data[field_name] = self._convert_to_model(field_value, core_type)
                        elif isinstance(field_value, list):
                            converted_data[field_name] = [
                                self._convert_to_model(item, core_type) if isinstance(item, dict) else item
                                for item in field_value
                            ]
                        else:
                            converted_data[field_name] = field_value
                        is_model_field = True
                        break

                if not is_model_field:
                    converted_data[field_name] = field_value
            else:
                converted_data[field_name] = field_value

        return model_class(**converted_data)

    async def _prepare_query_resolution(
        self,
        root_query_name: str,
        root_field_selection: Any,
        entity: type,
        query_method: Callable
    ) -> Tuple[Optional[Any], Optional[str], Optional[Dict]]:
        """
        Prepare query resolution (Phase 1: Serial)

        Args:
            root_query_name: Root query field name
            root_field_selection: Parsed field selection
            entity: Entity class
            query_method: @query decorated method

        Returns:
            Tuple of (typed_data, error_message, error_dict)
            - Success: (typed_data, None, None)
            - Failure: (None, error_message, error_dict)
        """
        logger.debug(f"[Phase 1] Preparing query: {root_query_name}")

        try:
            # 1. Execute query method
            args = root_field_selection.arguments or {}
            root_data = await self._execute_method(query_method, args, "query")
            logger.debug(f"[Phase 1] Query method executed: {root_query_name}")

            # 2. Build response model
            response_model = self.builder.build_response_model(
                entity=entity,
                field_selection=root_field_selection
            )
            logger.debug(f"[Phase 1] Response model built: {root_query_name}")

            # 3. Transform to response model
            if isinstance(root_data, list):
                typed_data = [
                    response_model.model_validate(
                        d.model_dump() if hasattr(d, 'model_dump') else d
                    )
                    for d in root_data
                ]
            elif root_data is not None:
                typed_data = response_model.model_validate(
                    root_data.model_dump() if hasattr(root_data, 'model_dump') else root_data
                )
            else:
                typed_data = None

            logger.debug(f"[Phase 1] Data transformed: {root_query_name}")
            return typed_data, None, None

        except GraphQLError as e:
            logger.warning(f"[Phase 1] GraphQL error preparing {root_query_name}: {e.message}")
            return None, e.message, e.to_dict()
        except Exception as e:
            logger.exception(f"[Phase 1] Unexpected error preparing {root_query_name}")
            error_dict = {
                "message": str(e),
                "extensions": {"code": type(e).__name__}
            }
            return None, str(e), error_dict

    async def _resolve_query_data(
        self,
        root_query_name: str,
        typed_data: Any,
        is_list: bool
    ) -> Tuple[Optional[Any], Optional[Dict]]:
        """
        Resolve query data (Phase 2: Concurrent)

        Args:
            root_query_name: Root query field name
            typed_data: Typed Pydantic data
            is_list: Whether data is a list

        Returns:
            Tuple of (result_data, error_dict)
            - Success: (result_data, None)
            - Failure: (None, error_dict)
        """
        logger.debug(f"[Phase 2] Resolving query: {root_query_name}")

        try:
            result_data = None

            if typed_data is not None:
                resolver = self.resolver_class(enable_from_attribute_in_type_adapter=self.enable_from_attribute_in_type_adapter)

                if is_list:
                    result = await resolver.resolve(typed_data)
                    if result is not None:
                        result_data = [r.model_dump(by_alias=True) for r in result]
                    else:
                        result_data = []
                else:
                    result = await resolver.resolve(typed_data)
                    if result is not None:
                        result_data = result.model_dump(by_alias=True)
                    else:
                        result_data = None
            else:
                result_data = [] if is_list else None

            logger.debug(f"[Phase 2] Query resolved: {root_query_name}")
            return result_data, None

        except Exception as e:
            logger.exception(f"[Phase 2] Error resolving {root_query_name}")
            error_dict = {
                "message": f"Resolution failed for {root_query_name}: {str(e)}",
                "extensions": {"code": type(e).__name__}
            }
            return None, error_dict

    async def _execute_concurrent_resolutions(
        self,
        resolution_tasks: List[Tuple[str, Any, bool]]
    ) -> Dict[str, Tuple[Optional[Any], Optional[Dict]]]:
        """
        Execute multiple query resolutions concurrently, using semaphore to control concurrency

        Args:
            resolution_tasks: List of (query_name, typed_data, is_list) tuples

        Returns:
            Dict mapping query_name to (result_data, error_dict)
        """
        if not resolution_tasks:
            return {}

        logger.info(f"[Phase 2] Starting concurrent resolution of {len(resolution_tasks)} queries")

        # Resource control: Only limit concurrent Resolver instances if user explicitly sets environment variable
        max_concurrency_str = os.getenv("PYDANTIC_RESOLVE_MAX_CONCURRENT_QUERIES")
        if max_concurrency_str:
            max_concurrency = int(max_concurrency_str)
            semaphore = asyncio.Semaphore(max_concurrency) if max_concurrency > 0 else None
        else:
            semaphore = None

        async def resolve_with_semaphore(query_name: str, typed_data: Any, is_list: bool):
            if semaphore:
                async with semaphore:
                    return await self._resolve_query_data(query_name, typed_data, is_list)
            else:
                return await self._resolve_query_data(query_name, typed_data, is_list)

        # Execute all resolution tasks concurrently
        results = await asyncio.gather(
            *[resolve_with_semaphore(name, data, is_list) for name, data, is_list in resolution_tasks],
            return_exceptions=True
        )

        # Process results and map to query names
        query_names = [name for name, _, _ in resolution_tasks]
        resolution_map = {}

        for query_name, result in zip(query_names, results):
            if isinstance(result, Exception):
                logger.exception(f"[Phase 2] Unexpected exception for {query_name}")
                error_dict = {
                    "message": f"Unexpected error: {str(result)}",
                    "extensions": {"code": type(result).__name__}
                }
                resolution_map[query_name] = (None, error_dict)
            else:
                resolution_map[query_name] = result

        logger.info("[Phase 2] Completed concurrent resolution")
        return resolution_map
