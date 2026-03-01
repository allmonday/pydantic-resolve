"""
Data structures for GraphQL functionality.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(eq=False)  # We'll implement custom __eq__ and __hash__
class FieldSelection:
    """Represents a selected field in GraphQL query."""
    alias: Optional[str] = None
    sub_fields: Optional[Dict[str, 'FieldSelection']] = None
    arguments: Optional[Dict[str, Any]] = None

    def __hash__(self):
        """Make FieldSelection hashable for caching.

        Note: arguments are intentionally excluded from hash
        as they don't affect the model structure.
        """
        sub_fields_hash = None
        if self.sub_fields:
            sub_fields_hash = tuple(
                (name, hash(sel))
                for name, sel in sorted(self.sub_fields.items())
            )
        return hash((self.alias, sub_fields_hash))

    def __eq__(self, other):
        if not isinstance(other, FieldSelection):
            return False
        # Compare alias and sub_fields, exclude arguments
        return (self.alias == other.alias and
                self.sub_fields == other.sub_fields)


@dataclass
class ParsedQuery:
    """Represents a parsed GraphQL query."""
    field_tree: Dict[str, FieldSelection]
    variables: Dict[str, Any] = field(default_factory=dict)
    operation_name: Optional[str] = None
