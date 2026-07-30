"""GraphQL utilities."""

from __future__ import annotations


def group_type_name(entity_name: str, group_suffix: str) -> str:
    """Return the group OBJECT type name an entity's operations live on.

    Under the grouped layout each entity's ``@query`` / ``@mutation`` methods
    become the fields of a ``{Entity}Query`` / ``{Entity}Mutation`` type.
    Centralizing the formula keeps the SDL generator, the introspection
    generator, and the executor's error messages from drifting apart.

    Args:
        entity_name: The owning entity class name (also the root mount field).
        group_suffix: ``"Query"`` or ``"Mutation"``.

    Examples:
        >>> group_type_name("User", "Query")
        'UserQuery'
        >>> group_type_name("Post", "Mutation")
        'PostMutation'
    """
    return f"{entity_name}{group_suffix}"
