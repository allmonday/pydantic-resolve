from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from pydantic_resolve.contrib.sqlalchemy import build_relationship

from pydantic_resolve import ErDiagram, config_resolver

from .conftest import (
    CourseDTO,
    CourseOrm,
    SchoolDTO,
    SchoolOrm,
    StudentDTO,
    StudentOrm,
    StudentProfileDTO,
    StudentProfileOrm,
    student_course,
)


def _find_student(item):
    return next(row for row in item if row.id == 1)


def _find_by_id(items, item_id: int):
    return next(item for item in items if item.id == item_id)


def test_build_relationship_can_feed_add_relationship(orm_mappings, session_factory):
    entities = build_relationship(mappings=orm_mappings, session_factory=session_factory)

    diagram = ErDiagram(configs=[]).add_relationship(entities)

    assert {cfg.kls for cfg in diagram.configs} == {StudentDTO, SchoolDTO, CourseDTO}


@pytest.mark.asyncio
async def test_resolver_with_built_relationship(
    orm_mappings,
    session_factory,
    session_maker,
    seeded_db,
):
    entities = build_relationship(mappings=orm_mappings, session_factory=session_factory)

    diagram = ErDiagram(configs=[]).add_relationship(entities)
    AutoLoad = diagram.create_auto_load()

    class StudentView(StudentDTO):
        model_config = ConfigDict(from_attributes=True)

        school: Annotated[SchoolDTO | None, AutoLoad()] = None
        courses: Annotated[list[CourseDTO], AutoLoad()] = []

    MyResolver = config_resolver("SQLAlchemyContribResolver", er_diagram=diagram)

    async with session_maker() as session:
        students = (
            await session.execute(select(StudentOrm).order_by(StudentOrm.id))
        ).scalars().all()

    payload = [
        StudentView(id=student.id, name=student.name, school_id=student.school_id)
        for student in students
    ]
    result = await MyResolver().resolve(payload)

    first = _find_student(result)
    second = next(row for row in result if row.id == 2)
    third = next(row for row in result if row.id == 3)

    assert first.school == SchoolDTO(id=1, name="School-A")
    assert sorted(c.title for c in first.courses) == ["Math", "Science"]

    assert second.school == SchoolDTO(id=1, name="School-A")
    assert [c.title for c in second.courses] == ["Science"]

    assert third.school == SchoolDTO(id=2, name="School-B")
    assert third.courses == []


@pytest.mark.asyncio
async def test_build_relationship_with_default_filter(
    session_factory,
    session_maker,
    seeded_db,
):
    async with session_maker() as session:
        async with session.begin():
            session.add_all(
                [
                    SchoolOrm(id=99, name="Deleted-School", deleted=True),
                    StudentOrm(id=4, name="Dan", school_id=99, deleted=False),
                    CourseOrm(id=99, title="Deleted-Course", deleted=True),
                ]
            )
            await session.execute(
                student_course.insert(),
                [{"student_id": 1, "course_id": 99}],
            )

    entities = build_relationship(
        mappings=[
            (StudentDTO, StudentOrm),
            (SchoolDTO, SchoolOrm),
            (CourseDTO, CourseOrm),
        ],
        session_factory=session_factory,
        default_filter=lambda cls: [cls.deleted.is_(False)],
    )

    diagram = ErDiagram(configs=[]).add_relationship(entities)
    AutoLoad = diagram.create_auto_load()

    class StudentView(StudentDTO):
        model_config = ConfigDict(from_attributes=True)

        school: Annotated[SchoolDTO | None, AutoLoad()] = None
        courses: Annotated[list[CourseDTO], AutoLoad()] = []

    MyResolver = config_resolver("SQLAlchemyContribFilteredResolver", er_diagram=diagram)

    async with session_maker() as session:
        students = (
            await session.execute(select(StudentOrm).order_by(StudentOrm.id))
        ).scalars().all()

    payload = [
        StudentView(id=student.id, name=student.name, school_id=student.school_id)
        for student in students
    ]

    result = await MyResolver().resolve(payload)
    student1 = _find_by_id(result, 1)
    student4 = _find_by_id(result, 4)

    assert sorted(c.title for c in student1.courses) == ["Math", "Science"]
    assert student4.school is None


@pytest.mark.asyncio
async def test_mapping_filter_empty_list_resets_global_default(
    session_factory,
    session_maker,
    seeded_db,
):
    async with session_maker() as session:
        async with session.begin():
            session.add_all(
                [
                    SchoolOrm(id=99, name="Deleted-School", deleted=True),
                    StudentOrm(id=4, name="Dan", school_id=99, deleted=False),
                ]
            )

    entities = build_relationship(
        mappings=[
            (StudentDTO, StudentOrm),
            (SchoolDTO, SchoolOrm, []),
            (CourseDTO, CourseOrm),
        ],
        session_factory=session_factory,
        default_filter=lambda cls: [cls.deleted.is_(False)],
    )

    diagram = ErDiagram(configs=[]).add_relationship(entities)
    AutoLoad = diagram.create_auto_load()

    class StudentView(StudentDTO):
        model_config = ConfigDict(from_attributes=True)

        school: Annotated[SchoolDTO | None, AutoLoad()] = None

    MyResolver = config_resolver("SQLAlchemyContribResetResolver", er_diagram=diagram)

    async with session_maker() as session:
        students = (
            await session.execute(select(StudentOrm).order_by(StudentOrm.id))
        ).scalars().all()

    payload = [
        StudentView(id=student.id, name=student.name, school_id=student.school_id)
        for student in students
    ]
    result = await MyResolver().resolve(payload)

    student4 = _find_by_id(result, 4)
    assert student4.school == SchoolDTO(id=99, name="Deleted-School")


@pytest.mark.asyncio
async def test_mapping_filter_non_empty_overrides_global_default(
    session_factory,
    session_maker,
    seeded_db,
):
    async with session_maker() as session:
        async with session.begin():
            session.add_all(
                [
                    SchoolOrm(id=99, name="Deleted-School", deleted=True),
                    StudentOrm(id=4, name="Dan", school_id=99, deleted=False),
                    CourseOrm(id=99, title="Deleted-Course", deleted=True),
                ]
            )
            await session.execute(
                student_course.insert(),
                [{"student_id": 1, "course_id": 99}],
            )

    entities = build_relationship(
        mappings=[
            (StudentDTO, StudentOrm),
            (SchoolDTO, SchoolOrm, [SchoolOrm.deleted.is_(True)]),
            (CourseDTO, CourseOrm, [CourseOrm.deleted.is_(True)]),
        ],
        session_factory=session_factory,
        default_filter=lambda cls: [cls.deleted.is_(False)],
    )

    diagram = ErDiagram(configs=[]).add_relationship(entities)
    AutoLoad = diagram.create_auto_load()

    class StudentView(StudentDTO):
        model_config = ConfigDict(from_attributes=True)

        school: Annotated[SchoolDTO | None, AutoLoad()] = None
        courses: Annotated[list[CourseDTO], AutoLoad()] = []

    MyResolver = config_resolver("SQLAlchemyContribOverrideResolver", er_diagram=diagram)

    async with session_maker() as session:
        students = (
            await session.execute(select(StudentOrm).order_by(StudentOrm.id))
        ).scalars().all()

    payload = [
        StudentView(id=student.id, name=student.name, school_id=student.school_id)
        for student in students
    ]
    result = await MyResolver().resolve(payload)

    student1 = _find_by_id(result, 1)
    student4 = _find_by_id(result, 4)

    assert student4.school == SchoolDTO(id=99, name="Deleted-School")
    assert [c.title for c in student1.courses] == ["Deleted-Course"]


@pytest.mark.asyncio
async def test_contrib_loader_uses_query_meta_fields(
    session_factory,
    session_maker,
    seeded_db,
):
    class SchoolNameDTO(BaseModel):
        model_config = ConfigDict(from_attributes=True)

        name: str

    class CourseTitleDTO(BaseModel):
        model_config = ConfigDict(from_attributes=True)

        title: str

    entities = build_relationship(
        mappings=[
            (StudentDTO, StudentOrm),
            (SchoolNameDTO, SchoolOrm),
            (CourseTitleDTO, CourseOrm),
        ],
        session_factory=session_factory,
    )

    diagram = ErDiagram(configs=[]).add_relationship(entities)
    AutoLoad = diagram.create_auto_load()

    class StudentView(StudentDTO):
        model_config = ConfigDict(from_attributes=True)

        school: Annotated[SchoolNameDTO | None, AutoLoad()] = None
        courses: Annotated[list[CourseTitleDTO], AutoLoad()] = []

    MyResolver = config_resolver("SQLAlchemyContribQueryMetaResolver", er_diagram=diagram)

    async with session_maker() as session:
        students = (
            await session.execute(select(StudentOrm).order_by(StudentOrm.id))
        ).scalars().all()

    payload = [
        StudentView(id=student.id, name=student.name, school_id=student.school_id)
        for student in students
    ]
    resolver = MyResolver()
    result = await resolver.resolve(payload)

    first = _find_student(result)
    assert first.school == SchoolNameDTO(name="School-A")
    assert sorted(course.title for course in first.courses) == ["Math", "Science"]

    school_loader = next(
        loader
        for path, loader in resolver.loader_instance_cache.items()
        if "_school_" in path
    )
    courses_loader = next(
        loader
        for path, loader in resolver.loader_instance_cache.items()
        if "_courses_" in path
    )

    assert set(school_loader._query_meta["fields"]) == {"name"}
    assert set(school_loader._effective_query_fields) == {"name", "id"}
    assert set(courses_loader._query_meta["fields"]) == {"title"}
    assert set(courses_loader._effective_query_fields) == {"title", "id"}


@pytest.mark.asyncio
async def test_resolver_with_reverse_one_to_one(
    session_factory,
    session_maker,
    seeded_db,
):
    entities = build_relationship(
        mappings=[
            (StudentDTO, StudentOrm),
            (StudentProfileDTO, StudentProfileOrm),
        ],
        session_factory=session_factory,
    )

    diagram = ErDiagram(configs=[]).add_relationship(entities)
    AutoLoad = diagram.create_auto_load()

    class StudentView(StudentDTO):
        model_config = ConfigDict(from_attributes=True)

        profile: Annotated[StudentProfileDTO | None, AutoLoad()] = None

    MyResolver = config_resolver("SA_RO2OResolver", er_diagram=diagram)

    async with session_maker() as session:
        students = (
            await session.execute(select(StudentOrm).order_by(StudentOrm.id))
        ).scalars().all()

    payload = [
        StudentView(id=student.id, name=student.name, school_id=student.school_id)
        for student in students
    ]
    result = await MyResolver().resolve(payload)

    alice = _find_by_id(result, 1)
    bob = _find_by_id(result, 2)
    cathy = _find_by_id(result, 3)

    assert alice.profile == StudentProfileDTO(id=100, student_id=1, nickname="ali")
    assert bob.profile is None
    assert cathy.profile == StudentProfileDTO(id=300, student_id=3, nickname="cat")
