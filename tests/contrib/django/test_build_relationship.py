from __future__ import annotations

from typing import Annotated

from asgiref.sync import sync_to_async
import pytest
from django.db.models import Q
from pydantic import BaseModel, ConfigDict

from pydantic_resolve import ErDiagram, config_resolver
from pydantic_resolve.contrib.django import build_relationship
from pydantic_resolve.contrib.mapping import Mapping

from tests.contrib.django.dto import CourseDTO, SchoolDTO, StudentDTO
from tests.contrib.django.models import CourseOrm, SchoolOrm, StudentOrm


async def _run_sync(fn):
    return await sync_to_async(fn, thread_sensitive=True)()


def _find_student(items):
    return next(row for row in items if row.id == 1)


def _find_by_id(items, item_id: int):
    return next(item for item in items if item.id == item_id)


def test_build_relationship_can_feed_add_relationship(django_schema, orm_mappings):
    entities = build_relationship(mappings=orm_mappings)

    diagram = ErDiagram(entities=[]).add_relationship(entities)

    assert {cfg.kls for cfg in diagram.entities} == {StudentDTO, SchoolDTO, CourseDTO}


@pytest.mark.asyncio
async def test_resolver_with_built_relationship(orm_mappings, seeded_db):
    entities = build_relationship(mappings=orm_mappings)

    diagram = ErDiagram(entities=[]).add_relationship(entities)
    AutoLoad = diagram.create_auto_load()

    class StudentView(StudentDTO):
        model_config = ConfigDict(from_attributes=True)

        school: Annotated[SchoolDTO | None, AutoLoad()] = None
        courses: Annotated[list[CourseDTO], AutoLoad()] = []

    MyResolver = config_resolver("DjangoContribResolver", er_diagram=diagram)

    students = await _run_sync(lambda: list(StudentOrm.objects.order_by("id")))

    payload = [
        StudentView(id=student.id, name=student.name, school_id=student.school_id)
        for student in students
    ]
    result = await MyResolver().resolve(payload)

    first = _find_student(result)
    second = next(row for row in result if row.id == 2)
    third = next(row for row in result if row.id == 3)

    assert first.school == SchoolDTO(id=1, name="School-A")
    assert sorted(course.title for course in first.courses) == ["Math", "Science"]

    assert second.school == SchoolDTO(id=1, name="School-A")
    assert [course.title for course in second.courses] == ["Science"]

    assert third.school == SchoolDTO(id=2, name="School-B")
    assert third.courses == []


@pytest.mark.asyncio
async def test_build_relationship_with_default_filter(seeded_db):
    await _run_sync(lambda: SchoolOrm.objects.create(id=99, name="Deleted-School", deleted=True))
    await _run_sync(lambda: StudentOrm.objects.create(id=4, name="Dan", school_id=99, deleted=False))
    deleted_course = await _run_sync(
        lambda: CourseOrm.objects.create(id=99, title="Deleted-Course", deleted=True)
    )
    await _run_sync(lambda: StudentOrm.objects.get(id=1).courses.add(deleted_course))

    entities = build_relationship(
        mappings=[
            Mapping(entity=StudentDTO, orm=StudentOrm),
            Mapping(entity=SchoolDTO, orm=SchoolOrm),
            Mapping(entity=CourseDTO, orm=CourseOrm),
        ],
        default_filter=lambda cls: [Q(deleted=False)],
    )

    diagram = ErDiagram(entities=[]).add_relationship(entities)
    AutoLoad = diagram.create_auto_load()

    class StudentView(StudentDTO):
        model_config = ConfigDict(from_attributes=True)

        school: Annotated[SchoolDTO | None, AutoLoad()] = None
        courses: Annotated[list[CourseDTO], AutoLoad()] = []

    MyResolver = config_resolver("DjangoContribFilteredResolver", er_diagram=diagram)

    students = await _run_sync(lambda: list(StudentOrm.objects.order_by("id")))
    payload = [
        StudentView(id=student.id, name=student.name, school_id=student.school_id)
        for student in students
    ]

    result = await MyResolver().resolve(payload)
    student1 = _find_by_id(result, 1)
    student4 = _find_by_id(result, 4)

    assert sorted(course.title for course in student1.courses) == ["Math", "Science"]
    assert student4.school is None


@pytest.mark.asyncio
async def test_mapping_filter_empty_list_resets_global_default(seeded_db):
    await _run_sync(lambda: SchoolOrm.objects.create(id=99, name="Deleted-School", deleted=True))
    await _run_sync(lambda: StudentOrm.objects.create(id=4, name="Dan", school_id=99, deleted=False))

    entities = build_relationship(
        mappings=[
            Mapping(entity=StudentDTO, orm=StudentOrm),
            Mapping(entity=SchoolDTO, orm=SchoolOrm, filters=[]),
            Mapping(entity=CourseDTO, orm=CourseOrm),
        ],
        default_filter=lambda cls: [Q(deleted=False)],
    )

    diagram = ErDiagram(entities=[]).add_relationship(entities)
    AutoLoad = diagram.create_auto_load()

    class StudentView(StudentDTO):
        model_config = ConfigDict(from_attributes=True)

        school: Annotated[SchoolDTO | None, AutoLoad()] = None

    MyResolver = config_resolver("DjangoContribResetResolver", er_diagram=diagram)

    students = await _run_sync(lambda: list(StudentOrm.objects.order_by("id")))
    payload = [
        StudentView(id=student.id, name=student.name, school_id=student.school_id)
        for student in students
    ]
    result = await MyResolver().resolve(payload)

    student4 = _find_by_id(result, 4)
    assert student4.school == SchoolDTO(id=99, name="Deleted-School")


@pytest.mark.asyncio
async def test_mapping_filter_non_empty_overrides_global_default(seeded_db):
    await _run_sync(lambda: SchoolOrm.objects.create(id=99, name="Deleted-School", deleted=True))
    await _run_sync(lambda: StudentOrm.objects.create(id=4, name="Dan", school_id=99, deleted=False))
    deleted_course = await _run_sync(
        lambda: CourseOrm.objects.create(id=99, title="Deleted-Course", deleted=True)
    )
    await _run_sync(lambda: StudentOrm.objects.get(id=1).courses.add(deleted_course))

    entities = build_relationship(
        mappings=[
            Mapping(entity=StudentDTO, orm=StudentOrm),
            Mapping(entity=SchoolDTO, orm=SchoolOrm, filters=[Q(deleted=True)]),
            Mapping(entity=CourseDTO, orm=CourseOrm, filters=[Q(deleted=True)]),
        ],
        default_filter=lambda cls: [Q(deleted=False)],
    )

    diagram = ErDiagram(entities=[]).add_relationship(entities)
    AutoLoad = diagram.create_auto_load()

    class StudentView(StudentDTO):
        model_config = ConfigDict(from_attributes=True)

        school: Annotated[SchoolDTO | None, AutoLoad()] = None
        courses: Annotated[list[CourseDTO], AutoLoad()] = []

    MyResolver = config_resolver("DjangoContribOverrideResolver", er_diagram=diagram)

    students = await _run_sync(lambda: list(StudentOrm.objects.order_by("id")))
    payload = [
        StudentView(id=student.id, name=student.name, school_id=student.school_id)
        for student in students
    ]
    result = await MyResolver().resolve(payload)

    student1 = _find_by_id(result, 1)
    student4 = _find_by_id(result, 4)

    assert student4.school == SchoolDTO(id=99, name="Deleted-School")
    assert [course.title for course in student1.courses] == ["Deleted-Course"]


@pytest.mark.asyncio
async def test_contrib_loader_uses_query_meta_fields(seeded_db):
    class SchoolNameDTO(BaseModel):
        model_config = ConfigDict(from_attributes=True)

        name: str

    class CourseTitleDTO(BaseModel):
        model_config = ConfigDict(from_attributes=True)

        title: str

    entities = build_relationship(
        mappings=[
            Mapping(entity=StudentDTO, orm=StudentOrm),
            Mapping(entity=SchoolNameDTO, orm=SchoolOrm),
            Mapping(entity=CourseTitleDTO, orm=CourseOrm),
        ]
    )

    diagram = ErDiagram(entities=[]).add_relationship(entities)
    AutoLoad = diagram.create_auto_load()

    class StudentView(StudentDTO):
        model_config = ConfigDict(from_attributes=True)

        school: Annotated[SchoolNameDTO | None, AutoLoad()] = None
        courses: Annotated[list[CourseTitleDTO], AutoLoad()] = []

    MyResolver = config_resolver("DjangoContribQueryMetaResolver", er_diagram=diagram)

    students = await _run_sync(lambda: list(StudentOrm.objects.order_by("id")))
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