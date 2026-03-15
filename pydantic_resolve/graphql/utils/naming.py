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


def to_graphql_field_name(entity_name: str, method_name: str) -> str:
    """Generate GraphQL field name with entity prefix.

    Combines entity name and method name to create a unique GraphQL field name,
    avoiding conflicts between methods with the same name in different entities.

    Args:
        entity_name: The entity class name (e.g., "User", "UserEntity").
        method_name: The method name in snake_case (e.g., "get_all", "get_by_id").

    Returns:
        GraphQL field name in camelCase with entity prefix.

    Examples:
        >>> to_graphql_field_name("User", "get_all")
        'userGetAll'
        >>> to_graphql_field_name("User", "get_by_id")
        'userGetById'
        >>> to_graphql_field_name("Post", "create")
        'postCreate'
        >>> to_graphql_field_name("UserEntity", "get_all")
        'userEntityGetAll'
    """
    # Entity prefix: first letter lowercase, rest unchanged
    entity_prefix = entity_name[0].lower() + entity_name[1:]
    # Method name to camelCase
    method_camel = to_camel_case(method_name)
    # Combine: entityPrefix + MethodCamel (capitalize first letter of method)
    return f"{entity_prefix}{method_camel[0].upper()}{method_camel[1:]}"
