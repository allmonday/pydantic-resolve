"""
Type registry and data structures for GraphQL schema generation.

This module provides the core data structures that represent GraphQL types
and a registry to manage them as a single source of truth.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class ArgumentInfo:
    """Represents an argument for a field (used in Query/Mutation fields)."""
    name: str
    python_type: type
    graphql_type_name: str
    is_list: bool = False
    is_optional: bool = False
    default_value: Optional[str] = None
    description: Optional[str] = None


@dataclass
class FieldInfo:
    """Represents a field in a GraphQL type."""
    name: str
    python_type: type
    graphql_type_name: str
    is_list: bool = False
    is_optional: bool = False
    description: Optional[str] = None
    is_relationship: bool = False
    relationship_target: Optional[str] = None
    args: List[ArgumentInfo] = field(default_factory=list)
    is_deprecated: bool = False
    deprecation_reason: Optional[str] = None


@dataclass
class TypeInfo:
    """Represents a GraphQL type (OBJECT, INPUT_OBJECT, SCALAR, etc.)."""
    name: str
    kind: str  # OBJECT, INPUT_OBJECT, SCALAR, LIST, NON_NULL
    python_class: Optional[type] = None
    fields: Dict[str, FieldInfo] = field(default_factory=dict)
    description: Optional[str] = None
    interfaces: List[str] = field(default_factory=list)
    enum_values: Optional[List[str]] = None
    is_input: bool = False


# Standard GraphQL scalar types
SCALAR_TYPES: Dict[str, TypeInfo] = {
    "Int": TypeInfo(
        name="Int",
        kind="SCALAR",
        description="The `Int` scalar type represents non-fractional signed whole numeric values."
    ),
    "Float": TypeInfo(
        name="Float",
        kind="SCALAR",
        description="The `Float` scalar type represents signed double-precision fractional values."
    ),
    "String": TypeInfo(
        name="String",
        kind="SCALAR",
        description="The `String` scalar type represents textual data."
    ),
    "Boolean": TypeInfo(
        name="Boolean",
        kind="SCALAR",
        description="The `Boolean` scalar type represents `true` or `false`."
    ),
    "ID": TypeInfo(
        name="ID",
        kind="SCALAR",
        description="The `ID` scalar type represents a unique identifier."
    ),
}


class TypeRegistry:
    """
    Central registry for all GraphQL types.

    Acts as a single source of truth for type information during schema generation.
    Both SDL and Introspection generators use this registry to ensure consistency.
    """

    def __init__(self):
        self._types: Dict[str, TypeInfo] = {}
        self._scalars: set = {'Int', 'Float', 'String', 'Boolean', 'ID'}

        # Register standard scalars
        for name, type_info in SCALAR_TYPES.items():
            self._types[name] = type_info

    def register(self, type_info: TypeInfo) -> None:
        """Register a type in the registry."""
        self._types[type_info.name] = type_info

    def get(self, name: str) -> Optional[TypeInfo]:
        """Get a type by name."""
        return self._types.get(name)

    def has(self, name: str) -> bool:
        """Check if a type exists in the registry."""
        return name in self._types

    def get_all_types(self) -> List[TypeInfo]:
        """Get all registered types."""
        return list(self._types.values())

    def get_output_types(self) -> List[TypeInfo]:
        """Get all OBJECT types (not INPUT_OBJECT or SCALAR)."""
        return [
            t for t in self._types.values()
            if t.kind == "OBJECT"
        ]

    def get_input_types(self) -> List[TypeInfo]:
        """Get all INPUT_OBJECT types."""
        return [
            t for t in self._types.values()
            if t.kind == "INPUT_OBJECT"
        ]

    def get_scalar_names(self) -> set:
        """Get all scalar type names."""
        return self._scalars.copy()

    def is_scalar(self, name: str) -> bool:
        """Check if a type is a scalar."""
        return name in self._scalars

    def clear_custom_types(self) -> None:
        """Clear all custom types (keep scalars)."""
        self._types = {
            name: type_info for name, type_info in self._types.items()
            if name in self._scalars
        }
