"""Naming conversion utilities for GraphQL."""

from __future__ import annotations


def to_camel_case(name: str) -> str:
    """Convert snake_case to camelCase.

    Args:
        name: A snake_case string.

    Returns:
        A camelCase string.

    Examples:
        >>> to_camel_case("get_all")
        'getAll'
        >>> to_camel_case("todo_add")
        'todoAdd'
        >>> to_camel_case("get_by_id")
        'getById'
        >>> to_camel_case("create_user")
        'createUser'
    """
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])
