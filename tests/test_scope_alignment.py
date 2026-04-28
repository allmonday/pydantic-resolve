"""Scope alignment validation tests.

Validates that ScopeRegistry entries stay aligned with:
1. Entity classes that have corresponding AutoLoad fields
2. AutoLoad chain in the view model

Run independently — no runtime dependencies.
"""

import types
import typing

from pydantic_resolve.utils.er_diagram import _get_pydantic_field_items_with_load_by


# ── Helpers ──


def _unwrap_type(annotation):
    """Unwrap Annotated[list[T], ...] / list[T] / T | None -> inner class T."""
    origin = typing.get_origin(annotation)

    # Annotated[X, ...] -> X
    if origin is typing.Annotated:
        args = typing.get_args(annotation)
        if args:
            return _unwrap_type(args[0])

    # list[T] -> T
    if origin is list:
        args = typing.get_args(annotation)
        if args:
            return _unwrap_type(args[0])

    # T | None -> T
    if origin is types.UnionType:
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return _unwrap_type(args[0])

    # Bare class (not a container) — return as-is if it's a class
    if isinstance(annotation, type):
        return annotation

    return None


def extract_autoload_field_names(view_class: type) -> set[str]:
    """Walk AutoLoad annotations and collect all field names in the chain."""
    names: set[str] = set()
    _walk(view_class, names, set())
    return names


def _walk(kls, names: set[str], visited: set):
    if kls in visited:
        return
    visited.add(kls)
    for field_name, annotation, _loader_info in _get_pydantic_field_items_with_load_by(kls):
        names.add(field_name)
        inner = _unwrap_type(annotation)
        if inner and isinstance(inner, type):
            _walk(inner, names, visited)


# ── Tests ──


def test_scope_registry_matches_autoload_chain():
    """Every scope_registry.scope_key must appear in UserScopeView's AutoLoad chain."""
    from demo.rbac.scope import scope_registry
    from demo.rbac.schemas import UserScopeView

    autoload_names = extract_autoload_field_names(UserScopeView)
    registry_keys = {entry.scope_key for entry in scope_registry.entries}

    missing = registry_keys - autoload_names
    assert missing == set(), f"Registry keys missing from AutoLoad chain: {missing}"


def test_scope_registry_entries_are_valid():
    """ScopeRegistry entries must have valid resource_type and scope_key."""
    from demo.rbac.scope import scope_registry

    for entry in scope_registry.entries:
        assert entry.resource_type, f"Empty resource_type in entry: {entry}"
        assert entry.scope_key, f"Empty scope_key in entry: {entry}"
        assert isinstance(entry.entity_kls, type), f"entity_kls not a type: {entry.entity_kls}"
