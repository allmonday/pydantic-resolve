from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Mapping:
    entity: type
    orm: type
    filters: list[Any] | None = None


def normalize_mappings(
    mappings: list[Mapping],
) -> tuple[list[tuple[type, type]], dict[type, type], dict[type, list[Any]]]:
    normalized: list[tuple[type, type]] = []
    orm_to_entity: dict[type, type] = {}
    orm_filter_overrides: dict[type, list[Any]] = {}
    seen_pairs: set[tuple[type, type]] = set()

    for m in mappings:
        if m.filters is not None:
            if not isinstance(m.filters, list):
                raise TypeError(
                    f"Invalid mapping filter for {m.orm}: expected list, got {type(m.filters).__name__}"
                )
            orm_filter_overrides[m.orm] = list(m.filters)

        pair = (m.entity, m.orm)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        # Allow DTO -> ORM many-to-one mappings.
        # The first DTO seen for a target ORM is used as relationship target inference default.
        orm_to_entity.setdefault(m.orm, m.entity)
        normalized.append(pair)

    return normalized, orm_to_entity, orm_filter_overrides
