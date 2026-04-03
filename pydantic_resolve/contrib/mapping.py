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

    for m in mappings:
        if m.filters is not None:
            if not isinstance(m.filters, list):
                raise TypeError(
                    f"Invalid mapping filter for {m.orm}: expected list, got {type(m.filters).__name__}"
                )
            orm_filter_overrides[m.orm] = list(m.filters)

        prev = orm_to_entity.get(m.orm)
        if prev is not None and prev is not m.entity:
            raise ValueError(
                f"Duplicate ORM mapping detected for {m.orm}: {prev} vs {m.entity}"
            )

        orm_to_entity[m.orm] = m.entity
        normalized.append((m.entity, m.orm))

    return normalized, orm_to_entity, orm_filter_overrides
