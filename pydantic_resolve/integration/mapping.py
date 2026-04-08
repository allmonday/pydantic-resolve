from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Mapping(BaseModel):
    entity: type
    orm: type
    filters: list[Any] | None = None


def _is_from_attributes_enabled(entity: type[BaseModel]) -> bool:
    return bool(entity.model_config.get("from_attributes"))


def _validate_mapping_entity(entity: type) -> None:
    if not isinstance(entity, type) or not issubclass(entity, BaseModel):
        raise TypeError(
            "Mapping.entity must be a subclass of pydantic.BaseModel, "
            f"got {entity!r}"
        )

    if not _is_from_attributes_enabled(entity):
        raise ValueError(
            f"{entity.__name__} must set model_config = ConfigDict(from_attributes=True) "
            "for ORM mapping"
        )


def normalize_mappings(
    mappings: list[Mapping],
) -> tuple[list[tuple[type, type]], dict[type, type], dict[type, list[Any]]]:
    normalized: list[tuple[type, type]] = []
    orm_to_entity: dict[type, type] = {}
    orm_filter_overrides: dict[type, list[Any]] = {}

    for m in mappings:
        _validate_mapping_entity(m.entity)

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
