"""Helper for querying GraphQL introspection data.

This module provides the IntrospectionQueryHelper class which analyzes GraphQL
introspection data to find all entity types that are reachable from a given
operation's return type. This is essential for progressive disclosure in MCP -
allowing us to return only the relevant type information for a specific query
or mutation.
"""

from __future__ import annotations

from typing import Any

from pydantic_resolve.graphql.types import (
    GraphQLField,
    GraphQLType,
    GraphQLTypeRef,
    IntrospectionData,
)


class IntrospectionQueryHelper:
    """Helper for querying introspection data to find related GraphQL types.

    This class analyzes GraphQL introspection data to find all entity types
    that are reachable from a given operation's return type. It handles
    LIST and NON_NULL type wrappers and follows relationship fields.

    The collected types can then be used to provide focused schema information
    in MCP progressive disclosure, rather than returning the entire schema.
    """

    def __init__(self, introspection_data: IntrospectionData, entity_names: set[str]):
        """Initialize the helper.

        Args:
            introspection_data: Full GraphQL introspection data from
                IntrospectionGenerator.generate()
            entity_names: Set of entity type names to consider when tracing.
                These are the types defined in the ErDiagram.
        """
        self._introspection: IntrospectionData = introspection_data
        self._entity_names: set[str] = entity_names
        self._type_cache: dict[str, GraphQLType] = {}
        self._build_type_cache()

    @property
    def introspection(self) -> IntrospectionData:
        """Get the full introspection data."""
        return self._introspection

    def _build_type_cache(self) -> None:
        """Build a cache of type name to type info for quick lookup."""
        for type_info in self._introspection.get("types", []):
            name = type_info.get("name")
            if name:
                self._type_cache[name] = type_info

    def collect_related_types(self, type_ref: GraphQLTypeRef | None) -> set[str]:
        """Collect all related types reachable from the given type reference.

        Recursively traces through LIST and NON_NULL wrappers and follows:
        - OBJECT fields (entity output types)
        - INPUT_OBJECT fields (operation argument/input types)
        - ENUM leaf types

        Args:
            type_ref: GraphQL type reference from introspection data

        Returns:
            Set of related type names that are reachable from the given type

        Example:
            >>> helper.collect_related_types({"kind": "OBJECT", "name": "User", "ofType": None})
            {'User', 'Post', 'Comment'}  # If User has relationships to Post and Comment
        """
        if type_ref is None:
            return set()

        visited: set[str] = set()

        def trace(ref: GraphQLTypeRef | None) -> None:
            if ref is None:
                return

            kind = ref.get("kind")
            name = ref.get("name")
            of_type = ref.get("ofType")

            if kind == "OBJECT" and name in self._entity_names:
                if name not in visited:
                    visited.add(name)
                    type_info = self._type_cache.get(name)
                    if type_info:
                        for field in type_info.get("fields", []) or []:
                            trace(field.get("type"))

            elif kind == "INPUT_OBJECT" and name:
                if name not in visited:
                    visited.add(name)
                    type_info = self._type_cache.get(name)
                    if type_info:
                        for field in type_info.get("inputFields", []) or []:
                            trace(field.get("type"))

            elif kind == "ENUM" and name:
                visited.add(name)

            elif kind == "LIST":
                trace(of_type)

            elif kind == "NON_NULL":
                trace(of_type)

        trace(type_ref)
        return visited

    def get_introspection_for_types(self, type_names: set[str]) -> list[GraphQLType]:
        """Get introspection data for the specified type names.

        Args:
            type_names: Set of type names to retrieve

        Returns:
            List of introspection type info dictionaries, sorted by name

        Example:
            >>> helper.get_introspection_for_types({'User', 'Post'})
            [{'name': 'Post', 'kind': 'OBJECT', ...}, {'name': 'User', 'kind': 'OBJECT', ...}]
        """
        result: list[GraphQLType] = []
        for name in sorted(type_names):
            type_info = self._type_cache.get(name)
            if type_info:
                result.append(type_info)
        return result

    def get_operation_field(
        self, operation_type: str, field_name: str
    ) -> GraphQLField | None:
        """Get a specific field from Query or Mutation type.

        Args:
            operation_type: "Query" or "Mutation"
            field_name: Name of the field/operation to retrieve

        Returns:
            Field introspection data or None if not found

        Example:
            >>> helper.get_operation_field("Query", "userGetAll")
            {'name': 'userGetAll', 'args': [...], 'type': {...}}
        """
        type_info = self._type_cache.get(operation_type)
        if not type_info:
            return None

        for field in type_info.get("fields", []) or []:
            if field.get("name") == field_name:
                return field

        return None

    def list_operation_fields(
        self, operation_type: str
    ) -> list[dict[str, str | None]]:
        """List all fields (operations) for Query or Mutation type.

        Returns lightweight operation info suitable for Layer 1 progressive disclosure.

        Args:
            operation_type: "Query" or "Mutation"

        Returns:
            List of dictionaries with 'name' and 'description' keys

        Example:
            >>> helper.list_operation_fields("Query")
            [{'name': 'userGetAll', 'description': 'Get all users'},
             {'name': 'userGetById', 'description': 'Get user by ID'}]
        """
        type_info = self._type_cache.get(operation_type)
        if not type_info:
            return []

        result: list[dict[str, str | None]] = []
        for field in type_info.get("fields", []) or []:
            result.append({
                "name": field.get("name"),
                "description": field.get("description"),
            })

        return result

    def get_operation_with_related_types(
        self, operation_type: str, field_name: str
    ) -> dict[str, Any] | None:
        """Get operation field info with all related types.

        Combines operation field info with introspection data for all related types.
        Useful for Layer 2 progressive disclosure.

        Args:
            operation_type: "Query" or "Mutation"
            field_name: Name of the field/operation

        Returns:
            Dictionary with 'operation' and 'related_types' keys, or None if not found

        Example:
            >>> helper.get_operation_with_related_types("Query", "userGetAll")
            {
                'operation': {'name': 'userGetAll', 'args': [...], 'type': {...}},
                'related_types': [
                    {'name': 'User', 'kind': 'OBJECT', ...},
                    {'name': 'Post', 'kind': 'OBJECT', ...}
                ]
            }
        """
        field = self.get_operation_field(operation_type, field_name)
        if not field:
            return None

        type_ref = field.get("type")
        related_type_names = self.collect_related_types(type_ref)
        related_types = self.get_introspection_for_types(related_type_names)

        return {
            "operation": field,
            "related_types": related_types,
        }
