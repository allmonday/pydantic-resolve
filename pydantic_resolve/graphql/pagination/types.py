"""
Simple limit/offset pagination types for GraphQL.

Provides:
- PageArgs: limit/offset pagination parameters
- PageLoadCommand: DataLoader key for paginated loading
- Pagination: metadata (hasMore, totalCount)
- create_result_type: dynamic {Entity}Result model factory
"""

from dataclasses import dataclass
from typing import Any, Optional

from pydantic import BaseModel, Field, create_model


class Pagination(BaseModel):
    """Pagination metadata returned alongside items."""
    has_more: bool = False
    total_count: Optional[int] = None


@dataclass(frozen=True)
class PageArgs:
    """Pagination parameters extracted from GraphQL field arguments."""
    limit: Optional[int] = None
    offset: int = 0
    default_page_size: int = 20
    max_page_size: int = 100

    @property
    def effective_limit(self) -> int:
        """Resolve the effective page size."""
        if self.limit is not None:
            return min(self.limit, self.max_page_size)
        return self.default_page_size


@dataclass(frozen=True)
class PageLoadCommand:
    """Key sent to a paginated DataLoader.

    The loader's batch_load_fn receives a list of these commands.
    All commands in a single batch share the same PageArgs
    (guaranteed by GraphQL query structure).
    """
    fk_value: Any
    page_args: PageArgs


def _build_pagination_model(pagination_selection: set[str]) -> type[BaseModel]:
    """Create a Pagination model containing only the selected fields."""
    fields = {}
    if 'has_more' in pagination_selection:
        fields['has_more'] = (bool, False)
    if 'total_count' in pagination_selection:
        fields['total_count'] = (Optional[int], None)

    if not fields:
        return Pagination

    return create_model('Pagination', **fields)


def create_result_type(
    item_type: type[BaseModel],
    pagination_selection: Optional[set[str]] = None,
) -> type[BaseModel]:
    """Create a Result type parameterized by item_type.

    Args:
        item_type: The model type for list items.
        pagination_selection: Set of selected pagination field names
            (e.g. {'has_more', 'total_count'}).  When provided, the
            generated Pagination model only contains the requested fields.
            When None, the Result model only contains items (no pagination).

    Example:
        PostResult = create_result_type(PostResponse)
    Produces a model with:
        items: list[PostResponse]
        pagination: Pagination
    """
    model_name = f"{item_type.__name__}Result"

    fields: dict[str, Any] = {
        'items': (list[item_type], Field(default_factory=list)),
    }

    if pagination_selection:
        pag_model = _build_pagination_model(pagination_selection)
        fields['pagination'] = (pag_model, Field(default_factory=pag_model))

    return create_model(
        model_name,
        __config__={"from_attributes": True} if getattr(item_type, "model_config", {}).get("from_attributes") else {},
        **fields,
    )
