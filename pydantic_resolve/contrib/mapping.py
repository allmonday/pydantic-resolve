from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Mapping(BaseModel):
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
            orm_filter_overrides[m.orm] = list(m.filters)

        if m.orm in orm_to_entity:
            raise ValueError(
                f"ORM {m.orm.__name__} is already mapped to "
                f"{orm_to_entity[m.orm].__name__}, cannot also map to {m.entity.__name__}"
            )
        orm_to_entity[m.orm] = m.entity
        normalized.append((m.entity, m.orm))

    return normalized, orm_to_entity, orm_filter_overrides
