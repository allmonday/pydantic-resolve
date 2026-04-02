from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import ConfigDict
from tortoise.expressions import Q

from pydantic_resolve import ErDiagram, config_resolver
from pydantic_resolve.contrib.tortoise import build_relationship

from .conftest import CourseDTO, CourseOrm, SchoolDTO, SchoolOrm, StudentDTO, StudentOrm


def _find_student(items):
    return next(row for row in items if row.id == 1)


def _find_by_id(items, item_id: int):
    return next(item for item in items if item.id == item_id)


def test_build_relationship_can_feed_add_relationship(tortoise_db, orm_mappings):
    entities = build_relationship(mappings=orm_mappings)

    diagram = ErDiagram(configs=[]).add_relationship(entities)

    assert {cfg.kls for cfg in diagram.configs} == {StudentDTO, SchoolDTO, CourseDTO}


@pytest.mark.asyncio
async def test_resolver_with_built_relationship(orm_mappings, seeded_db):
    entities = build_relationship(mappings=orm_mappings)

    diagram = ErDiagram(configs=[]).add_relationship(entities)
    AutoLoad = diagram.create_auto_load()

    class StudentView(StudentDTO):
        model_config = ConfigDict(from_attributes=True)

        school: Annotated[SchoolDTO | None, AutoLoad()] = None
        courses: Annotated[list[CourseDTO], AutoLoad()] = []

    MyResolver = config_resolver("TortoiseContribResolver", er_diagram=diagram)

    students = await StudentOrm.all().order_by("id")

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
async def test_build_relationship_with_default_filter(seeded_db):
    await SchoolOrm.create(id=99, name="Deleted-School", deleted=True)
    await StudentOrm.create(id=4, name="Dan", school_id=99, deleted=False)
    deleted_course = await CourseOrm.create(id=99, title="Deleted-Course", deleted=True)
    student = await StudentOrm.get(id=1)
    await student.courses.add(deleted_course)

    entities = build_relationship(
        mappings=[
            (StudentDTO, StudentOrm),
            (SchoolDTO, SchoolOrm),
            (CourseDTO, CourseOrm),
        ],
        default_filter=lambda cls: [Q(deleted=False)],
    )

    diagram = ErDiagram(configs=[]).add_relationship(entities)
    AutoLoad = diagram.create_auto_load()

    class StudentView(StudentDTO):
        model_config = ConfigDict(from_attributes=True)

        school: Annotated[SchoolDTO | None, AutoLoad()] = None
        courses: Annotated[list[CourseDTO], AutoLoad()] = []

    MyResolver = config_resolver("TortoiseContribFilteredResolver", er_diagram=diagram)

    students = await StudentOrm.all().order_by("id")
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
async def test_mapping_filter_empty_list_resets_global_default(seeded_db):
    await SchoolOrm.create(id=99, name="Deleted-School", deleted=True)
    await StudentOrm.create(id=4, name="Dan", school_id=99, deleted=False)

    entities = build_relationship(
        mappings=[
            (StudentDTO, StudentOrm),
            (SchoolDTO, SchoolOrm, []),
            (CourseDTO, CourseOrm),
        ],
        default_filter=lambda cls: [Q(deleted=False)],
    )

    diagram = ErDiagram(configs=[]).add_relationship(entities)
    AutoLoad = diagram.create_auto_load()

    class StudentView(StudentDTO):
        model_config = ConfigDict(from_attributes=True)

        school: Annotated[SchoolDTO | None, AutoLoad()] = None

    MyResolver = config_resolver("TortoiseContribResetResolver", er_diagram=diagram)

    students = await StudentOrm.all().order_by("id")
    payload = [
        StudentView(id=student.id, name=student.name, school_id=student.school_id)
        for student in students
    ]
    result = await MyResolver().resolve(payload)

    student4 = _find_by_id(result, 4)
    assert student4.school == SchoolDTO(id=99, name="Deleted-School")


@pytest.mark.asyncio
async def test_mapping_filter_non_empty_overrides_global_default(seeded_db):
    await SchoolOrm.create(id=99, name="Deleted-School", deleted=True)
    await StudentOrm.create(id=4, name="Dan", school_id=99, deleted=False)
    deleted_course = await CourseOrm.create(id=99, title="Deleted-Course", deleted=True)
    student = await StudentOrm.get(id=1)
    await student.courses.add(deleted_course)

    entities = build_relationship(
        mappings=[
            (StudentDTO, StudentOrm),
            (SchoolDTO, SchoolOrm, [Q(deleted=True)]),
            (CourseDTO, CourseOrm, [Q(deleted=True)]),
        ],
        default_filter=lambda cls: [Q(deleted=False)],
    )

    diagram = ErDiagram(configs=[]).add_relationship(entities)
    AutoLoad = diagram.create_auto_load()

    class StudentView(StudentDTO):
        model_config = ConfigDict(from_attributes=True)

        school: Annotated[SchoolDTO | None, AutoLoad()] = None
        courses: Annotated[list[CourseDTO], AutoLoad()] = []

    MyResolver = config_resolver("TortoiseContribOverrideResolver", er_diagram=diagram)

    students = await StudentOrm.all().order_by("id")
    payload = [
        StudentView(id=student.id, name=student.name, school_id=student.school_id)
        for student in students
    ]
    result = await MyResolver().resolve(payload)

    student1 = _find_by_id(result, 1)
    student4 = _find_by_id(result, 4)

    assert student4.school == SchoolDTO(id=99, name="Deleted-School")
    assert [c.title for c in student1.courses] == ["Deleted-Course"]