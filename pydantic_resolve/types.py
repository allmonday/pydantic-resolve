"""Core types for enriched DataLoader keys and access scope constraints."""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ScopeFilter:
    """Access scope constraint for DataLoader queries.

    Two modes (can coexist):
    - ids: set of allowed entity IDs (RBAC, converted from permission tree)
    - apply: closure that appends WHERE clause to query (ABAC)

    Loader applies both: ids -> WHERE id IN (...), apply -> closure(stmt).
    For per-key batching: loader unions all ids, then post-filters each group.
    """

    ids: frozenset[int] | None = None
    apply: Callable[[Any], Any] | None = None


@dataclass
class ScopeNode:
    """A node in the access scope tree.

    The scope tree is carried on entities via ``_access_scope_tree`` attribute.
    Format: ``None | 'all' | 'empty' | list[ScopeNode]``.

    Each node targets a relationship field (``type``) and constrains which
    entity IDs are accessible (``ids``), optionally with a SQL WHERE closure
    (``apply``) and nested constraints for child relationships (``children``).
    """

    type: str  # Relationship / field name to match
    ids: list[int] | None = None  # None=unconstrained, []=empty, [1,2,...]=concrete
    apply: Callable[[Any], Any] | None = None  # SQL WHERE closure for ABAC
    children: list['ScopeNode'] | None = None  # Nested scope nodes

    def to_scope_filter(self) -> ScopeFilter:
        """Convert this node to a flat ScopeFilter for DataLoader consumption."""
        ids = frozenset(self.ids) if self.ids else None
        return ScopeFilter(ids=ids, apply=self.apply)


@dataclass(frozen=True)
class LoadCommand:
    """Base class for enriched DataLoader keys.

    Layers (graphql pagination, permission scope) populate optional fields.
    The DataLoader inspects the fields it understands and ignores the rest.
    """

    fk_value: Any
    page_args: Any = None  # PageArgs | None (set by graphql layer)
    scope_filter: ScopeFilter | None = None  # set by permission system
