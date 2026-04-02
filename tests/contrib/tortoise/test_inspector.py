from __future__ import annotations

import logging
from typing import get_args, get_origin

import pytest
from pydantic import BaseModel, ConfigDict, computed_field

from pydantic_resolve.contrib.tortoise import build_relationship

from .conftest import CourseDTO, CourseOrm, SchoolDTO, SchoolOrm, StudentDTO, StudentOrm


def _find_entity(entities, target_kls):
    return next(item for item in entities if item.kls is target_kls)


def _find_relationship(entity, rel_name: str):
    return next(rel for rel in entity.relationships if rel.name == rel_name)


def test_inspector_builds_relationships_for_m2o_o2m_m2m(tortoise_db, orm_mappings):
    entities = build_relationship(mappings=orm_mappings)

    student_entity = _find_entity(entities, StudentDTO)
    school_rel = _find_relationship(student_entity, "school")
    courses_rel = _find_relationship(student_entity, "courses")

    assert school_rel.fk == "school_id"
    assert school_rel.target is SchoolDTO
    assert school_rel.load_many is False

    assert courses_rel.fk == "id"
    assert get_origin(courses_rel.target) is list
    assert get_args(courses_rel.target)[0] is CourseDTO
    assert courses_rel.load_many is False

    school_entity = _find_entity(entities, SchoolDTO)
    students_rel = _find_relationship(school_entity, "students")

    assert students_rel.fk == "id"
    assert get_origin(students_rel.target) is list
    assert get_args(students_rel.target)[0] is StudentDTO
    assert students_rel.load_many is False


def test_inspector_skips_unmapped_targets_with_warning(tortoise_db, caplog):
    with caplog.at_level(logging.WARNING):
        entities = build_relationship(mappings=[(StudentDTO, StudentOrm)])

    assert entities == []
    assert len(caplog.records) >= 1


def test_inspector_raises_on_invalid_mapping_filter_type(tortoise_db):
    with pytest.raises(TypeError, match="Invalid mapping filter"):
        build_relationship(
            mappings=[
                (StudentDTO, StudentOrm),
                (SchoolDTO, SchoolOrm, "not-a-list"),  # type: ignore[arg-type]
            ]
        )


def test_inspector_raises_when_default_filter_returns_non_list(tortoise_db):
    with pytest.raises(TypeError, match="default_filter"):
        build_relationship(
            mappings=[
                (StudentDTO, StudentOrm),
                (SchoolDTO, SchoolOrm),
                (CourseDTO, CourseOrm),
            ],
            default_filter=lambda cls: object(),  # type: ignore[return-value]
        )


class _SchoolDTOWithMissingRequiredField(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    missing: str


def test_inspector_raises_when_required_dto_scalar_field_missing_in_orm(tortoise_db):
    with pytest.raises(ValueError, match="Required DTO fields not found in ORM scalar fields"):
        build_relationship(mappings=[(_SchoolDTOWithMissingRequiredField, SchoolOrm)])


class _SchoolDTOWithOptionalAndComputedFields(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    extra: str = "fallback"

    @computed_field
    @property
    def label(self) -> str:
        return f"{self.id}-{self.name}"


def test_inspector_skips_default_and_computed_fields_in_dto_validation(
    tortoise_db,
):
    entities = build_relationship(
        mappings=[
            (StudentDTO, StudentOrm),
            (_SchoolDTOWithOptionalAndComputedFields, SchoolOrm),
            (CourseDTO, CourseOrm),
        ]
    )

    school_entity = _find_entity(entities, _SchoolDTOWithOptionalAndComputedFields)
    students_rel = _find_relationship(school_entity, "students")

    assert students_rel.name == "students"
