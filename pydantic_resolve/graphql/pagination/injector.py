"""
Pagination injection hook for GraphQL nested pagination.

Injects PageArgs from parent's pagination tree into resolved children
before the resolver traverses them.
"""

import pydantic_resolve.constant as const


def inject_nested_pagination(parent: object, field_name: str, result: object) -> None:
    """Inject nested PageArgs from parent's pagination tree into resolved children.

    Handles two cases:
    1. _result fields (paginated lists): result is a Result model with 'items'
    2. Many-to-one fields: result is a single Pydantic model instance
    """
    tree = getattr(parent, const.GRAPHQL_PAGINATION_TREE_FIELD, None)
    if not tree or field_name not in tree:
        return

    _, nested_tree = tree[field_name]
    if not nested_tree:
        return

    # Case 1: Result model has 'items' attribute (paginated list)
    items = getattr(result, 'items', None)
    if items:
        for item in items:
            for nested_name, (nested_pa, deeper_tree) in nested_tree.items():
                key = f'{const.GRAPHQL_PAGINATION_FIELD_PREFIX}{nested_name}'
                if hasattr(item, key):
                    object.__setattr__(item, key, nested_pa)
            # Propagate the nested tree for deeper levels
            if hasattr(item, const.GRAPHQL_PAGINATION_TREE_FIELD):
                object.__setattr__(item, const.GRAPHQL_PAGINATION_TREE_FIELD, nested_tree)
        return

    # Case 2: Many-to-one field (single model instance)
    if hasattr(result, '__dict__'):
        for nested_name, (nested_pa, deeper_tree) in nested_tree.items():
            key = f'{const.GRAPHQL_PAGINATION_FIELD_PREFIX}{nested_name}'
            if hasattr(result, key):
                object.__setattr__(result, key, nested_pa)
        if hasattr(result, const.GRAPHQL_PAGINATION_TREE_FIELD):
            object.__setattr__(result, const.GRAPHQL_PAGINATION_TREE_FIELD, nested_tree)
