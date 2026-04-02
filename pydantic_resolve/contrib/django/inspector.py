from __future__ import annotations

import logging
from typing import Any, Callable

from pydantic_resolve.contrib.django.loader import (
    create_many_to_many_loader,
    create_many_to_one_loader,
    create_one_to_many_loader,
    create_reverse_one_to_one_loader,
)
from pydantic_resolve.utils.er_diagram import Entity, Relationship

logger = logging.getLogger(__name__)


Mapping = tuple[type, type] | tuple[type, type, list[Any]]


def _normalize_mappings(
    mappings: list[Mapping],
) -> tuple[list[tuple[type, type]], dict[type, type], dict[type, list[Any]]]:
    normalized_mappings: list[tuple[type, type]] = []
    orm_to_dto: dict[type, type] = {}
    orm_filter_overrides: dict[type, list[Any]] = {}

    for mapping in mappings:
        if len(mapping) == 2:
            dto_kls, orm_kls = mapping
        elif len(mapping) == 3:
            dto_kls, orm_kls, filter_override = mapping
            if not isinstance(filter_override, list):
                raise TypeError(
                    f"Invalid mapping filter for {orm_kls}: expected list, got {type(filter_override).__name__}"
                )
            orm_filter_overrides[orm_kls] = list(filter_override)
        else:
            raise TypeError(
                f"Invalid mapping item length {len(mapping)}: expected 2 or 3"
            )

        prev = orm_to_dto.get(orm_kls)
        if prev is not None and prev is not dto_kls:
            raise ValueError(
                f"Duplicate ORM mapping detected for {orm_kls}: {prev} vs {dto_kls}"
            )

        orm_to_dto[orm_kls] = dto_kls
        normalized_mappings.append((dto_kls, orm_kls))

    return normalized_mappings, orm_to_dto, orm_filter_overrides


def _resolve_target_filters(
    target_orm: type,
    orm_filter_overrides: dict[type, list[Any]],
    default_filter: Callable[[type], list[Any]] | None,
) -> list[Any]:
    if target_orm in orm_filter_overrides:
        return list(orm_filter_overrides[target_orm])

    if default_filter is None:
        return []

    resolved = default_filter(target_orm)
    if resolved is None:
        return []
    if not isinstance(resolved, list):
        raise TypeError(
            f"default_filter({target_orm.__name__}) must return list, got {type(resolved).__name__}"
        )
    return list(resolved)


def _validate_dto_scalar_fields(dto_kls: type, orm_kls: type) -> None:
    orm_scalar_fields = {field.attname for field in orm_kls._meta.concrete_fields}

    missing_required_fields = []
    for field_name, field_info in dto_kls.model_fields.items():
        if not field_info.is_required():
            continue
        if field_name not in orm_scalar_fields:
            missing_required_fields.append(field_name)

    if missing_required_fields:
        missing_str = ", ".join(sorted(missing_required_fields))
        raise ValueError(
            f"Required DTO fields not found in ORM scalar fields for mapping "
            f"{dto_kls.__name__} -> {orm_kls.__name__}: {missing_str}"
        )


def _iter_relation_fields(orm_kls: type) -> list[Any]:
    return sorted(
        [field for field in orm_kls._meta.get_fields() if field.is_relation],
        key=lambda field: field.name,
    )


def _inspect_orm_relationships(
    orm_kls: type,
    orm_to_dto: dict[type, type],
    using: Any,
    orm_filter_overrides: dict[type, list[Any]],
    default_filter: Callable[[type], list[Any]] | None,
) -> list[Relationship]:
    relationships: list[Relationship] = []

    for field in _iter_relation_fields(orm_kls):
        target_orm = getattr(field, "related_model", None)
        if target_orm is None:
            continue

        target_dto = orm_to_dto.get(target_orm)
        if target_dto is None:
            logger.warning(
                "Skipping relationship %s.%s: target ORM %s is not in mappings",
                orm_kls.__name__,
                field.name,
                target_orm.__name__,
            )
            continue

        filters = _resolve_target_filters(target_orm, orm_filter_overrides, default_filter)

        if field.many_to_one and not field.auto_created:
            relationships.append(
                Relationship(
                    fk=field.attname,
                    target=target_dto,
                    name=field.name,
                    loader=create_many_to_one_loader(
                        source_orm_kls=orm_kls,
                        rel_name=field.name,
                        target_orm_kls=target_orm,
                        target_dto_kls=target_dto,
                        target_remote_field_name=field.target_field.attname,
                        using=using,
                        filters=filters,
                    ),
                    load_many=False,
                )
            )
            continue

        if field.one_to_many:
            relationships.append(
                Relationship(
                    fk=field.target_field.attname,
                    target=list[target_dto],
                    name=field.name,
                    loader=create_one_to_many_loader(
                        source_orm_kls=orm_kls,
                        rel_name=field.name,
                        target_orm_kls=target_orm,
                        target_dto_kls=target_dto,
                        target_relation_field_name=field.field.attname,
                        using=using,
                        filters=filters,
                    ),
                    load_many=False,
                )
            )
            continue

        if field.one_to_one and not field.auto_created:
            relationships.append(
                Relationship(
                    fk=field.attname,
                    target=target_dto,
                    name=field.name,
                    loader=create_many_to_one_loader(
                        source_orm_kls=orm_kls,
                        rel_name=field.name,
                        target_orm_kls=target_orm,
                        target_dto_kls=target_dto,
                        target_remote_field_name=field.target_field.attname,
                        using=using,
                        filters=filters,
                    ),
                    load_many=False,
                )
            )
            continue

        if field.one_to_one and field.auto_created:
            relationships.append(
                Relationship(
                    fk=field.target_field.attname,
                    target=target_dto,
                    name=field.name,
                    loader=create_reverse_one_to_one_loader(
                        source_orm_kls=orm_kls,
                        rel_name=field.name,
                        target_orm_kls=target_orm,
                        target_dto_kls=target_dto,
                        target_relation_field_name=field.field.attname,
                        using=using,
                        filters=filters,
                    ),
                    load_many=False,
                )
            )
            continue

        if field.many_to_many:
            relationships.append(
                Relationship(
                    fk=orm_kls._meta.pk.attname,
                    target=list[target_dto],
                    name=field.name,
                    loader=create_many_to_many_loader(
                        source_orm_kls=orm_kls,
                        rel_name=field.name,
                        source_match_field_name=orm_kls._meta.pk.attname,
                        target_orm_kls=target_orm,
                        target_dto_kls=target_dto,
                        using=using,
                        filters=filters,
                    ),
                    load_many=False,
                )
            )

    return relationships


def build_relationship(
    *,
    mappings: list[Mapping],
    using: Any = None,
    default_filter: Callable[[type], list[Any]] | None = None,
) -> list[Entity]:
    normalized_mappings, orm_to_dto, orm_filter_overrides = _normalize_mappings(mappings)
    entities: list[Entity] = []

    for dto_kls, orm_kls in normalized_mappings:
        _validate_dto_scalar_fields(dto_kls, orm_kls)
        relationships = _inspect_orm_relationships(
            orm_kls=orm_kls,
            orm_to_dto=orm_to_dto,
            using=using,
            orm_filter_overrides=orm_filter_overrides,
            default_filter=default_filter,
        )
        if relationships:
            entities.append(Entity(kls=dto_kls, relationships=relationships))

    return entities
