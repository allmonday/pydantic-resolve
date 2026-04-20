"""
Type mapping utilities for GraphQL.

Provides centralized type conversion between Python and GraphQL types.
"""

from enum import Enum
from typing import get_origin, get_args, Union
from pydantic_resolve.utils.class_util import safe_issubclass
from pydantic_resolve.utils.types import get_core_types, _is_optional, _is_list
from pydantic import BaseModel


# Python basic types to GraphQL types mapping
PYTHON_TO_GQL_TYPES = {
    int: 'Int',
    str: 'String',
    float: 'Float',
    bool: 'Boolean',
}


def is_enum_type(python_type: type) -> bool:
    """
    Check if type is an Enum subclass.

    Args:
        python_type: Python type

    Returns:
        True if the type is an Enum subclass, False otherwise

    Examples:
        >>> from enum import Enum
        >>> class Status(Enum):
        ...     ACTIVE = "active"
        >>> is_enum_type(Status)
        True
        >>> is_enum_type(str)
        False
    """
    try:
        return safe_issubclass(python_type, Enum)
    except TypeError:
        return False


def get_enum_names(enum_class: type) -> list[str]:
    """
    Get all enum member names from an Enum class.

    Args:
        enum_class: An Enum subclass

    Returns:
        List of enum member names

    Examples:
        >>> from enum import Enum
        >>> class Status(Enum):
        ...     ACTIVE = "active"
        ...     INACTIVE = "inactive"
        >>> get_enum_values(Status)
        ['ACTIVE', 'INACTIVE']
    """
    if not is_enum_type(enum_class):
        return []
    return [member.name for member in enum_class]


def map_python_to_graphql(python_type: type, include_required: bool = True) -> str:
    """
    Map Python type to GraphQL type string

    Args:
        python_type: Python type
        include_required: Whether to include ! (non-null marker)

    Returns:
        GraphQL type string (e.g., "String!", "[Int]!")

    Examples:
        >>> map_python_to_graphql(int)
        "Int!"
        >>> map_python_to_graphql(list[int])
        "[Int]!"
        >>> map_python_to_graphql(Optional[str])
        "String"
    """
    # Check if it's Optional type (Union with None)
    is_optional = _is_optional(python_type)

    # For Optional types, don't include required suffix
    if is_optional:
        include_required = False

    required_suffix = "!" if include_required else ""

    # Use get_core_types to handle all wrapper types
    core_types = get_core_types(python_type)
    if not core_types:
        return "String" + required_suffix  # Default to String

    core_type = core_types[0]

    # Check if it's list type
    if _is_list(python_type):
        # list[T] -> [T!]!
        inner_gql = map_python_to_graphql(core_type, include_required=True)
        return f"[{inner_gql}]{required_suffix}"
    else:
        # T -> T!
        # Check if it's an enum type first
        if is_enum_type(core_type):
            return f"{core_type.__name__}{required_suffix}"
        elif safe_issubclass(core_type, BaseModel):
            return f"{core_type.__name__}{required_suffix}"
        else:
            # Scalar type
            scalar_name = map_scalar_type(core_type)
            return f"{scalar_name}{required_suffix}"


def map_scalar_type(python_type: type) -> str:
    """
    Map Python scalar type to GraphQL scalar type name

    Args:
        python_type: Python type

    Returns:
        GraphQL scalar type name ("Int", "String", "Boolean", "Float") or enum name

    Examples:
        >>> map_scalar_type(int)
        "Int"
        >>> map_scalar_type(str)
        "String"
    """
    # Check if it's an enum type - return enum class name as GraphQL type
    if is_enum_type(python_type):
        return python_type.__name__

    # Check direct mapping
    if python_type in PYTHON_TO_GQL_TYPES:
        return PYTHON_TO_GQL_TYPES[python_type]

    # Check via string (handle type strings, etc.)
    type_str = str(python_type).lower()
    if "int" in type_str:
        return "Int"
    elif "bool" in type_str:
        return "Boolean"
    elif "float" in type_str:
        return "Float"
    else:
        return "String"


def get_graphql_type_description(gql_type: str) -> str:
    """
    Get description of GraphQL scalar type

    Args:
        gql_type: GraphQL type name

    Returns:
        Type description string
    """
    descriptions = {
        "Int": "The `Int` scalar type represents non-fractional signed whole numeric values.",
        "Float": "The `Float` scalar type represents signed double-precision fractional values.",
        "String": "The `String` scalar type represents textual data.",
        "Boolean": "The `Boolean` scalar type represents `true` or `false`.",
        "ID": "The `ID` scalar type represents a unique identifier.",
    }
    return descriptions.get(gql_type)


def is_union_type(type_hint: type) -> bool:
    """
    Check if type is Union (including Optional)

    Args:
        type_hint: Type hint

    Returns:
        Whether it's a Union type
    """
    origin = get_origin(type_hint)
    return origin is Union


def is_list_type(type_hint: type) -> bool:
    """
    Check if type is list

    Args:
        type_hint: Type hint

    Returns:
        Whether it's a list type
    """
    return _is_list(type_hint)


def unwrap_optional(type_hint: type):
    """
    Extract T from Optional[T] or Union[T, None]

    Args:
        type_hint: Type hint

    Returns:
        If it's Optional[T], return T
        Otherwise return the original type

    Examples:
        >>> unwrap_optional(Optional[int])
        int
        >>> unwrap_optional(int)
        int
    """
    core_types = get_core_types(type_hint)
    # Filter out NoneType
    non_none_types = [t for t in core_types if t is not type(None)]
    return non_none_types[0] if non_none_types else type_hint


def extract_list_element_type(list_type: type):
    """
    Extract element type T from list[T]

    Args:
        list_type: List type

    Returns:
        Element type, or None if not a list

    Examples:
        >>> extract_list_element_type(list[int])
        int
    """
    if not is_list_type(list_type):
        return None

    args = get_args(list_type)
    if args:
        return args[0]
    return None
