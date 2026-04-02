from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from pydantic_resolve.contrib.sqlalchemy import build_relationship

from pydantic_resolve import ErDiagram, config_resolver

from .conftest import CourseDTO, SchoolDTO, StudentDTO, StudentOrm


def _find_student(item):
    return next(row for row in item if row.id == 1)


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
