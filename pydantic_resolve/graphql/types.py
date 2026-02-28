"""
Data structures for GraphQL functionality.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class FieldSelection:
    """Represents a selected field in GraphQL query."""
    alias: Optional[str] = None
    sub_fields: Optional[Dict[str, 'FieldSelection']] = None
    arguments: Optional[Dict[str, Any]] = None


@dataclass
class ParsedQuery:
    """Represents a parsed GraphQL query."""
    field_tree: Dict[str, FieldSelection]
    variables: Dict[str, Any] = field(default_factory=dict)
    operation_name: Optional[str] = None
