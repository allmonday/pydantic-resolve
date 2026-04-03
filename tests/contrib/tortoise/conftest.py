from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from pydantic import BaseModel, ConfigDict
from tortoise import Tortoise, fields
from tortoise.models import Model

from pydantic_resolve.contrib.mapping import Mapping


class SchoolOrm(Model):
    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=100)
    deleted = fields.BooleanField(default=False)

    class Meta:
        table = "school"


class StudentOrm(Model):
    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=100)
    deleted = fields.BooleanField(default=False)
    school = fields.ForeignKeyField("models.SchoolOrm", related_name="students")
    courses = fields.ManyToManyField(
        "models.CourseOrm",
        related_name="students",
        through="student_course",
    )

    class Meta:
        table = "student"


class CourseOrm(Model):
    id = fields.IntField(primary_key=True)
    title = fields.CharField(max_length=100)
    deleted = fields.BooleanField(default=False)

    class Meta:
        table = "course"


class SchoolDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class StudentDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    school_id: int


class CourseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str


@pytest.fixture
async def tortoise_db(tmp_path) -> AsyncIterator[None]:
    db_path = tmp_path / "tortoise_contrib.sqlite3"
    await Tortoise.init(
        db_url=f"sqlite://{db_path}",
        modules={"models": ["tests.contrib.tortoise.conftest"]},
        _enable_global_fallback=True,
    )
    await Tortoise.generate_schemas()

    try:
        yield
    finally:
        await Tortoise.close_connections()
        await Tortoise._reset_apps()


@pytest.fixture
async def seeded_db(tortoise_db) -> None:
    school_a = await SchoolOrm.create(id=1, name="School-A", deleted=False)
    school_b = await SchoolOrm.create(id=2, name="School-B", deleted=False)

    alice = await StudentOrm.create(
        id=1,
        name="Alice",
        school=school_a,
        deleted=False,
    )
    bob = await StudentOrm.create(
        id=2,
        name="Bob",
        school=school_a,
        deleted=False,
    )
    await StudentOrm.create(
        id=3,
        name="Cathy",
        school=school_b,
        deleted=False,
    )

    math = await CourseOrm.create(id=10, title="Math", deleted=False)
    science = await CourseOrm.create(id=20, title="Science", deleted=False)
    await CourseOrm.create(id=30, title="History", deleted=False)

    await alice.courses.add(math, science)
    await bob.courses.add(science)


@pytest.fixture
def orm_mappings() -> list[Mapping]:
    return [
        Mapping(entity=StudentDTO, orm=StudentOrm),
        Mapping(entity=SchoolDTO, orm=SchoolOrm),
        Mapping(entity=CourseDTO, orm=CourseOrm),
    ]
