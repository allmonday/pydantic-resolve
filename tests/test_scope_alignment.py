"""Scope alignment validation tests.

Validates that HIERARCHY levels stay aligned with:
1. Explicitly declared entry entities (x ⊆ y)
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


def test_hierarchy_subset_of_entry_entities():
    """HIERARCHY levels must be subset of declared entry entities (x ⊆ y)."""
    from demo.rbac.scope import HIERARCHY, SCOPE_ENTRY_ENTITIES, validate_scope_alignment

    unaligned = validate_scope_alignment(HIERARCHY, SCOPE_ENTRY_ENTITIES)
    assert unaligned == set(), f"Unaligned scope levels: {unaligned}"


def test_hierarchy_matches_autoload_chain():
    """Every HIERARCHY.relationship_name must appear in UserScopeView's AutoLoad chain."""
    from demo.rbac.scope import HIERARCHY
    from demo.rbac.schemas import UserScopeView

    autoload_names = extract_autoload_field_names(UserScopeView)
    hierarchy_names = {lvl.relationship_name for lvl in HIERARCHY}

    missing = hierarchy_names - autoload_names
    assert missing == set(), f"Missing from AutoLoad chain: {missing}"
