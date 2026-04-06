from __future__ import annotations

import logging
from typing import Any, Callable

from pydantic_resolve.contrib.mapping import Mapping, normalize_mappings
from pydantic_resolve.contrib.sqlalchemy.loader import (
    create_many_to_many_loader,
    create_many_to_one_loader,
    create_one_to_many_loader,
    create_reverse_one_to_one_loader,
)
from pydantic_resolve.utils.er_diagram import Entity, Relationship

logger = logging.getLogger(__name__)


def _expect_single_pair(pairs: Any, message: str) -> tuple[Any, Any]:
    pair_list = list(pairs)
    if len(pair_list) != 1:
        raise NotImplementedError(message)
    return pair_list[0]


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
    from sqlalchemy import inspect

    mapper = inspect(orm_kls)
    orm_scalar_fields = {attr.key for attr in mapper.column_attrs}

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


def _inspect_orm_relationships(
    orm_kls: type,
    orm_to_dto: dict[type, type],
    session_factory: Callable,
    orm_filter_overrides: dict[type, list[Any]],
    default_filter: Callable[[type], list[Any]] | None,
) -> list[Relationship]:
    # MANYTOONE: the FK column is on the *source* side (self).
    #   e.g.  Task.owner_id -> User.id
    #     class Task(Base):
    #         owner_id = Column(Integer, ForeignKey('user.id'))
    #         owner = relationship('User')          # MANYTOONE
    #
    # ONETOMANY: the FK column is on the *target* side.
    #   e.g.  User <- Task.user_id
    #     class User(Base):
    #         tasks = relationship('Task', back_populates='user')  # ONETOMANY (uselist=True)
    #   one-to-one variant (uselist=False):
    #     class User(Base):
    #         profile = relationship('Profile', uselist=False, back_populates='user')  # ONETOMANY (uselist=False)
    #
    # MANYTOMANY: requires a secondary (association) table.
    #   e.g.  Student <-> Course via student_course
    #     student_course = Table('student_course', Base.metadata,
    #         Column('student_id', ForeignKey('student.id')),
    #         Column('course_id',  ForeignKey('course.id')))
    #     class Student(Base):
    #         courses = relationship('Course', secondary=student_course)  # MANYTOMANY
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
        filters = _resolve_target_filters(
            target_orm=target_orm,
            orm_filter_overrides=orm_filter_overrides,
            default_filter=default_filter,
        )

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
                filters=filters,
            )

        elif direction is ONETOMANY:
            local_col, remote_col = _expect_single_pair(
                rel.local_remote_pairs,
                f"Composite FK is not supported for ONETOMANY: {orm_kls.__name__}.{rel.key}",
            )
            fk_field = local_col.key

            if rel.uselist is False:
                target_type = target_dto
                loader = create_reverse_one_to_one_loader(
                    source_orm_kls=orm_kls,
                    rel_name=rel.key,
                    target_orm_kls=target_orm,
                    target_dto_kls=target_dto,
                    target_fk_col_name=remote_col.key,
                    session_factory=session_factory,
                    filters=filters,
                )
            else:
                target_type = list[target_dto]
                loader = create_one_to_many_loader(
                    source_orm_kls=orm_kls,
                    rel_name=rel.key,
                    target_orm_kls=target_orm,
                    target_dto_kls=target_dto,
                    target_fk_col_name=remote_col.key,
                    session_factory=session_factory,
                    filters=filters,
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
                filters=filters,
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
    mappings: list[Mapping],
    session_factory: Callable,
    default_filter: Callable[[type], list[Any]] | None = None,
) -> list[Entity]:
    normalized_mappings, orm_to_dto, orm_filter_overrides = normalize_mappings(mappings)
    entities: list[Entity] = []

    for dto_kls, orm_kls in normalized_mappings:
        _validate_dto_scalar_fields(dto_kls, orm_kls)
        relationships = _inspect_orm_relationships(
            orm_kls=orm_kls,
            orm_to_dto=orm_to_dto,
            session_factory=session_factory,
            orm_filter_overrides=orm_filter_overrides,
            default_filter=default_filter,
        )
        if relationships:
            entities.append(Entity(kls=dto_kls, relationships=relationships))

    return entities
