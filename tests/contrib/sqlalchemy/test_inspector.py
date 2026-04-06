from __future__ import annotations

import logging
from typing import get_args, get_origin

import pytest
from pydantic import BaseModel, ValidationError, computed_field
from sqlalchemy import ForeignKeyConstraint, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pydantic_resolve.contrib.sqlalchemy import build_relationship
from pydantic_resolve.contrib.mapping import Mapping

from .conftest import CourseDTO, CourseOrm, SchoolDTO, SchoolOrm, StudentDTO, StudentOrm


def _dummy_session_factory():
    class _DummySession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    return _DummySession()


def _find_entity(entities, target_kls):
    return next(item for item in entities if item.kls is target_kls)


def _find_relationship(entity, rel_name: str):
    return next(rel for rel in entity.relationships if rel.name == rel_name)


def test_inspector_builds_relationships_for_m2o_o2m_m2m(orm_mappings):
    entities = build_relationship(
        mappings=orm_mappings,
        session_factory=_dummy_session_factory,
    )

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


def test_inspector_skips_unmapped_targets_with_warning(caplog):
    with caplog.at_level(logging.WARNING):
        entities = build_relationship(
            mappings=[Mapping(entity=StudentDTO, orm=StudentOrm)],
            session_factory=_dummy_session_factory,
        )

    assert entities == []
    assert len(caplog.records) >= 1


class _CompositeBase(DeclarativeBase):
    pass


class _ParentOrm(_CompositeBase):
    __tablename__ = "composite_parent"

    tenant_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)

    children: Mapped[list["_ChildOrm"]] = relationship(back_populates="parent")


class _ChildOrm(_CompositeBase):
    __tablename__ = "composite_child"

    tenant_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    parent_tenant_id: Mapped[int] = mapped_column(Integer)
    parent_id: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        ForeignKeyConstraint(
            ["parent_tenant_id", "parent_id"],
            ["composite_parent.tenant_id", "composite_parent.id"],
        ),
    )

    parent: Mapped[_ParentOrm] = relationship(back_populates="children")


class _ParentDTO(BaseModel):


    tenant_id: int
    id: int
    name: str


class _ChildDTO(BaseModel):


    tenant_id: int
    id: int
    parent_tenant_id: int
    parent_id: int


def test_inspector_raises_on_composite_foreign_key():
    with pytest.raises(NotImplementedError):
        build_relationship(
            mappings=[
                Mapping(entity=_ParentDTO, orm=_ParentOrm),
                Mapping(entity=_ChildDTO, orm=_ChildOrm)
            ],
            session_factory=_dummy_session_factory,
        )


def test_inspector_raises_on_invalid_mapping_filter_type():
    with pytest.raises(ValidationError, match="filters"):
        build_relationship(
            mappings=[
                Mapping(entity=StudentDTO, orm=StudentOrm),
                Mapping(entity=SchoolDTO, orm=SchoolOrm, filters="not-a-list"),  # type: ignore[arg-type]
            ],
            session_factory=_dummy_session_factory,
        )


def test_inspector_raises_when_default_filter_returns_non_list():
    with pytest.raises(TypeError, match="default_filter"):
        build_relationship(
            mappings=[
                Mapping(entity=StudentDTO, orm=StudentOrm),
                Mapping(entity=SchoolDTO, orm=SchoolOrm),
                Mapping(entity=CourseDTO, orm=CourseOrm),
            ],
            session_factory=_dummy_session_factory,
            default_filter=lambda cls: cls.deleted.is_(False),  # type: ignore[return-value]
        )


class _SchoolDTOWithMissingRequiredField(BaseModel):


    id: int
    name: str
    missing: str


def test_inspector_raises_when_required_dto_scalar_field_missing_in_orm():
    with pytest.raises(ValueError, match="Required DTO fields not found in ORM scalar fields"):
        build_relationship(
            mappings=[Mapping(entity=_SchoolDTOWithMissingRequiredField, orm=SchoolOrm)],
            session_factory=_dummy_session_factory,
        )


class _SchoolDTOWithOptionalAndComputedFields(BaseModel):


    id: int
    name: str
    extra: str = "fallback"

    @computed_field
    @property
    def label(self) -> str:
        return f"{self.id}-{self.name}"


def test_inspector_skips_default_and_computed_fields_in_dto_validation():
    entities = build_relationship(
        mappings=[
            Mapping(entity=StudentDTO, orm=StudentOrm),
            Mapping(entity=_SchoolDTOWithOptionalAndComputedFields, orm=SchoolOrm),
            Mapping(entity=CourseDTO, orm=CourseOrm),
        ],
        session_factory=_dummy_session_factory,
    )

    school_entity = _find_entity(entities, _SchoolDTOWithOptionalAndComputedFields)
    students_rel = _find_relationship(school_entity, "students")

    assert students_rel.name == "students"


def test_inspector_rejects_duplicate_orm_mapping():
    with pytest.raises(ValueError, match="SchoolOrm is already mapped to"):
        build_relationship(
            mappings=[
                Mapping(entity=StudentDTO, orm=StudentOrm),
                Mapping(entity=SchoolDTO, orm=SchoolOrm),
                Mapping(entity=SchoolDTO, orm=SchoolOrm),
                Mapping(entity=CourseDTO, orm=CourseOrm),
            ],
            session_factory=_dummy_session_factory,
        )
