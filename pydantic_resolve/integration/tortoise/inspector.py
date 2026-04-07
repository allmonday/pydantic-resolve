from __future__ import annotations

import logging
from typing import Any, Callable

from pydantic_resolve.integration.tortoise.loader import (
    create_many_to_many_loader,
    create_many_to_one_loader,
    create_one_to_many_loader,
    create_reverse_one_to_one_loader,
)
from pydantic_resolve.utils.er_diagram import Entity, Relationship
from pydantic_resolve.integration.mapping import Mapping, normalize_mappings

logger = logging.getLogger(__name__)


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
    orm_scalar_fields = set(orm_kls._meta.fields_db_projection.keys())

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


def _get_related_model(field: Any, orm_kls: type, rel_name: str) -> type:
    target_orm = getattr(field, "related_model", None)
    if target_orm is None:
        raise ValueError(
            f"Unresolved Tortoise relation {orm_kls.__name__}.{rel_name}. "
            "Call Tortoise.init() or Tortoise.init_models() before build_relationship()."
        )
    return target_orm


def _inspect_orm_relationships(
    orm_kls: type,
    orm_to_dto: dict[type, type],
    using_db: Any,
    orm_filter_overrides: dict[type, list[Any]],
    default_filter: Callable[[type], list[Any]] | None,
) -> list[Relationship]:
    # fk_fields (many_to_one, FK on self): meta.fk_fields
    #   e.g.  Task.owner_id -> User.id
    #     class Task(Model):
    #         owner = ForeignKeyField('models.User', related_name='tasks')
    #
    # backward_fk_fields (one_to_many, reverse side): meta.backward_fk_fields
    #   e.g.  User <- Task.owner (reverse of ForeignKeyField)
    #     # On User side: User.tasks (reverse OneToMany from Task.owner)
    #
    # o2o_fields (one_to_one, FK on self): meta.o2o_fields
    #   e.g.  User.profile_id -> Profile.id
    #     class User(Model):
    #         profile = OneToOneField('models.Profile', related_name='user')
    #
    # backward_o2o_fields (one_to_one reverse): meta.backward_o2o_fields
    #   e.g.  Profile <- User.profile (reverse of OneToOneField)
    #
    # m2m_fields (many_to_many): meta.m2m_fields
    #   e.g.  Student <-> Course
    #     class Student(Model):
    #         courses = ManyToManyField('models.Course', related_name='students')
    meta = orm_kls._meta
    relationships: list[Relationship] = []

    for rel_name in sorted(meta.fk_fields):
        field = meta.fields_map[rel_name]
        target_orm = _get_related_model(field, orm_kls, rel_name)
        target_dto = orm_to_dto.get(target_orm)
        if target_dto is None:
            logger.warning(
                "Skipping relationship %s.%s: target ORM %s is not in mappings",
                orm_kls.__name__,
                rel_name,
                target_orm.__name__,
            )
            continue

        filters = _resolve_target_filters(target_orm, orm_filter_overrides, default_filter)
        relationships.append(
            Relationship(
                fk=field.source_field,
                target=target_dto,
                name=rel_name,
                loader=create_many_to_one_loader(
                    source_orm_kls=orm_kls,
                    rel_name=rel_name,
                    target_orm_kls=target_orm,
                    target_dto_kls=target_dto,
                    target_remote_field_name=field.to_field or target_orm._meta.pk_attr,
                    using_db=using_db,
                    filters=filters,
                ),
                load_many=False,
            )
        )

    for rel_name in sorted(meta.backward_fk_fields):
        field = meta.fields_map[rel_name]
        target_orm = _get_related_model(field, orm_kls, rel_name)
        target_dto = orm_to_dto.get(target_orm)
        if target_dto is None:
            logger.warning(
                "Skipping relationship %s.%s: target ORM %s is not in mappings",
                orm_kls.__name__,
                rel_name,
                target_orm.__name__,
            )
            continue

        filters = _resolve_target_filters(target_orm, orm_filter_overrides, default_filter)
        relationships.append(
            Relationship(
                fk=field.to_field_instance.model_field_name,
                target=list[target_dto],
                name=rel_name,
                loader=create_one_to_many_loader(
                    source_orm_kls=orm_kls,
                    rel_name=rel_name,
                    target_orm_kls=target_orm,
                    target_dto_kls=target_dto,
                    target_relation_field_name=field.relation_source_field,
                    using_db=using_db,
                    filters=filters,
                )
            )
        )

    for rel_name in sorted(meta.o2o_fields):
        field = meta.fields_map[rel_name]
        target_orm = _get_related_model(field, orm_kls, rel_name)
        target_dto = orm_to_dto.get(target_orm)
        if target_dto is None:
            logger.warning(
                "Skipping relationship %s.%s: target ORM %s is not in mappings",
                orm_kls.__name__,
                rel_name,
                target_orm.__name__,
            )
            continue

        filters = _resolve_target_filters(target_orm, orm_filter_overrides, default_filter)
        relationships.append(
            Relationship(
                fk=field.source_field,
                target=target_dto,
                name=rel_name,
                loader=create_many_to_one_loader(
                    source_orm_kls=orm_kls,
                    rel_name=rel_name,
                    target_orm_kls=target_orm,
                    target_dto_kls=target_dto,
                    target_remote_field_name=field.to_field or target_orm._meta.pk_attr,
                    using_db=using_db,
                    filters=filters,
                )
            )
        )

    for rel_name in sorted(meta.backward_o2o_fields):
        field = meta.fields_map[rel_name]
        target_orm = _get_related_model(field, orm_kls, rel_name)
        target_dto = orm_to_dto.get(target_orm)
        if target_dto is None:
            logger.warning(
                "Skipping relationship %s.%s: target ORM %s is not in mappings",
                orm_kls.__name__,
                rel_name,
                target_orm.__name__,
            )
            continue

        filters = _resolve_target_filters(target_orm, orm_filter_overrides, default_filter)
        relationships.append(
            Relationship(
                fk=field.to_field_instance.model_field_name,
                target=target_dto,
                name=rel_name,
                loader=create_reverse_one_to_one_loader(
                    source_orm_kls=orm_kls,
                    rel_name=rel_name,
                    target_orm_kls=target_orm,
                    target_dto_kls=target_dto,
                    target_relation_field_name=field.relation_source_field,
                    using_db=using_db,
                    filters=filters,
                )
            )
        )

    for rel_name in sorted(meta.m2m_fields):
        field = meta.fields_map[rel_name]
        target_orm = _get_related_model(field, orm_kls, rel_name)
        target_dto = orm_to_dto.get(target_orm)
        if target_dto is None:
            logger.warning(
                "Skipping relationship %s.%s: target ORM %s is not in mappings",
                orm_kls.__name__,
                rel_name,
                target_orm.__name__,
            )
            continue

        filters = _resolve_target_filters(target_orm, orm_filter_overrides, default_filter)
        relationships.append(
            Relationship(
                fk=meta.pk_attr,
                target=list[target_dto],
                name=rel_name,
                loader=create_many_to_many_loader(
                    source_orm_kls=orm_kls,
                    rel_name=rel_name,
                    source_match_field_name=meta.pk_attr,
                    target_orm_kls=target_orm,
                    target_dto_kls=target_dto,
                    using_db=using_db,
                    filters=filters,
                )
            )
        )

    return relationships


def build_relationship(
    *,
    mappings: list[Mapping],
    using_db: Any = None,
    default_filter: Callable[[type], list[Any]] | None = None,
) -> list[Entity]:
    normalized_mappings, orm_to_dto, orm_filter_overrides = normalize_mappings(mappings)
    entities: list[Entity] = []

    for dto_kls, orm_kls in normalized_mappings:
        _validate_dto_scalar_fields(dto_kls, orm_kls)
        relationships = _inspect_orm_relationships(
            orm_kls=orm_kls,
            orm_to_dto=orm_to_dto,
            using_db=using_db,
            orm_filter_overrides=orm_filter_overrides,
            default_filter=default_filter,
        )
        if relationships:
            entities.append(Entity(kls=dto_kls, relationships=relationships))

    return entities
