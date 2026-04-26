"""Core types for enriched DataLoader keys and access scope constraints."""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ScopeFilter:
    """Access scope constraint for DataLoader queries.

    Three dimensions (can coexist):
    - is_all: unconstrained access (explicit boolean)
    - ids: set of allowed entity IDs (RBAC result)
    - filter_fn: closure that appends WHERE clause to query (ABAC rule)

    Loader applies all: is_all → skip ID filter, ids → WHERE id IN (...),
    filter_fn → closure(stmt).
    For per-key batching: loader unions all ids, then post-filters each group.
    """

    is_all: bool = False
    ids: frozenset[int] | None = None
    filter_fn: Callable[[Any], Any] | None = None


@dataclass
class ScopeNode:
    """A node in the access scope tree.

    The scope tree is carried on entities via ``_access_scope_tree`` attribute.
    Format: ``None | list[ScopeNode]``.

    Each node targets a relationship field (``type``) and carries:
    - is_all: unconstrained access at this level
    - ids: specific resource IDs from RBAC
    - filter_fn: ABAC attribute filter (SQL WHERE closure)
    - children: nested constraints for child relationships
    """

    type: str  # Relationship / field name to match
    is_all: bool = False  # True = unconstrained access
    ids: list[int] | None = None  # RBAC: specific resource IDs
    filter_fn: Callable[[Any], Any] | None = None  # ABAC: SQL WHERE closure
    children: list['ScopeNode'] | None = None  # Nested scope nodes

    def to_scope_filter(self) -> ScopeFilter:
        """Convert this node to a flat ScopeFilter for DataLoader consumption."""
        ids = frozenset(self.ids) if self.ids else None
        return ScopeFilter(is_all=self.is_all, ids=ids, filter_fn=self.filter_fn)


@dataclass(frozen=True)
class LoadCommand:
    """Base class for enriched DataLoader keys.

    Layers (graphql pagination, permission scope) populate optional fields.
    The DataLoader inspects the fields it understands and ignores the rest.
    """

    fk_value: Any
    page_args: Any = None  # PageArgs | None (set by graphql layer)
    scope_filter: ScopeFilter | None = None  # set by permission system
