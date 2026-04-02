from __future__ import annotations

import logging
from typing import Any, Callable

from pydantic_resolve.contrib.sqlalchemy.loader import (
    create_many_to_many_loader,
    create_many_to_one_loader,
    create_one_to_many_loader,
)
from pydantic_resolve.utils.er_diagram import Entity, Relationship

logger = logging.getLogger(__name__)


def _expect_single_pair(pairs: Any, message: str) -> tuple[Any, Any]:
    pair_list = list(pairs)
    if len(pair_list) != 1:
        raise NotImplementedError(message)
    return pair_list[0]


def _build_orm_to_dto_map(mappings: list[tuple[type, type]]) -> dict[type, type]:
    orm_to_dto: dict[type, type] = {}
    for dto_kls, orm_kls in mappings:
        prev = orm_to_dto.get(orm_kls)
        if prev is not None and prev is not dto_kls:
            raise ValueError(
                f"Duplicate ORM mapping detected for {orm_kls}: {prev} vs {dto_kls}"
            )
        orm_to_dto[orm_kls] = dto_kls
    return orm_to_dto


def _inspect_orm_relationships(
    orm_kls: type,
    orm_to_dto: dict[type, type],
    session_factory: Callable,
) -> list[Relationship]:
    from sqlalchemy import inspect
    from sqlalchemy.orm import MANYTOONE, ONETOMANY, MANYTOMANY

    mapper = inspect(orm_kls)
    relationships: list[Relationship] = []

    for rel in mapper.relationships:
        target_orm = rel.mapper.class_
        target_dto = orm_to_dto.get(target_orm)

        if target_dto is None:
            logger.warning(
                "Skipping relationship %s.%s: target ORM %s is not in mappings",
                orm_kls.__name__,
                rel.key,
                target_orm.__name__,
            )
            continue

        direction = rel.direction

        if direction is MANYTOONE:
            local_col, remote_col = _expect_single_pair(
                rel.local_remote_pairs,
                f"Composite FK is not supported for MANYTOONE: {orm_kls.__name__}.{rel.key}",
            )
            fk_field = local_col.key
            target_type = target_dto
            loader = create_many_to_one_loader(
                source_orm_kls=orm_kls,
                rel_name=rel.key,
                target_orm_kls=target_orm,
                target_dto_kls=target_dto,
                target_remote_col_name=remote_col.key,
                session_factory=session_factory,
            )

        elif direction is ONETOMANY:
            local_col, remote_col = _expect_single_pair(
                rel.local_remote_pairs,
                f"Composite FK is not supported for ONETOMANY: {orm_kls.__name__}.{rel.key}",
            )
            fk_field = local_col.key
            target_type = list[target_dto]
            loader = create_one_to_many_loader(
                source_orm_kls=orm_kls,
                rel_name=rel.key,
                target_orm_kls=target_orm,
                target_dto_kls=target_dto,
                target_fk_col_name=remote_col.key,
                session_factory=session_factory,
            )

        elif direction is MANYTOMANY:
            secondary = rel.secondary
            if secondary is None:
                raise NotImplementedError(
                    f"MANYTOMANY without secondary table is not supported: {orm_kls.__name__}.{rel.key}"
                )

            source_col, secondary_local_col = _expect_single_pair(
                rel.synchronize_pairs,
                f"Composite source pair is not supported for MANYTOMANY: {orm_kls.__name__}.{rel.key}",
            )
            target_col, secondary_remote_col = _expect_single_pair(
                rel.secondary_synchronize_pairs,
                f"Composite target pair is not supported for MANYTOMANY: {orm_kls.__name__}.{rel.key}",
            )

            fk_field = source_col.key
            target_type = list[target_dto]
            loader = create_many_to_many_loader(
                source_orm_kls=orm_kls,
                rel_name=rel.key,
                target_orm_kls=target_orm,
                target_dto_kls=target_dto,
                secondary_table=secondary,
                secondary_local_col_name=secondary_local_col.key,
                secondary_remote_col_name=secondary_remote_col.key,
                target_match_col_name=target_col.key,
                session_factory=session_factory,
            )

        else:
            raise NotImplementedError(
                f"Relationship direction {direction.name} is not supported: {orm_kls.__name__}.{rel.key}"
            )

        relationships.append(
            Relationship(
                fk=fk_field,
                target=target_type,
                name=rel.key,
                loader=loader,
                load_many=False,
            )
        )

    return relationships


def build_relationship(
    *,
    mappings: list[tuple[type, type]],
    session_factory: Callable,
) -> list[Entity]:
    orm_to_dto = _build_orm_to_dto_map(mappings)
    entities: list[Entity] = []

    for dto_kls, orm_kls in mappings:
        relationships = _inspect_orm_relationships(
            orm_kls=orm_kls,
            orm_to_dto=orm_to_dto,
            session_factory=session_factory,
        )
        if relationships:
            entities.append(Entity(kls=dto_kls, relationships=relationships))

    return entities
