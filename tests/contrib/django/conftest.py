from __future__ import annotations

from pathlib import Path
import tempfile

import django
import pytest
from django.conf import settings
from django.db import connection, connections
from pydantic import BaseModel

from tests.contrib.django.dto import CourseDTO, SchoolDTO, StudentDTO

DB_PATH = Path(tempfile.gettempdir()) / "pydantic_resolve_django_contrib.sqlite3"

if DB_PATH.exists():
    DB_PATH.unlink()

if not settings.configured:
    settings.configure(
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(DB_PATH),
            }
        },
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "tests.contrib.django.apps.DjangoContribTestAppConfig",
        ],
        SECRET_KEY="django-contrib-test",
        DEFAULT_AUTO_FIELD="django.db.models.AutoField",
        USE_TZ=True,
    )

django.setup()

from tests.contrib.django.models import CourseOrm, SchoolOrm, StudentOrm  # noqa: E402


@pytest.fixture(scope="session")
def django_schema():
    with connection.schema_editor() as editor:
        editor.create_model(SchoolOrm)
        editor.create_model(StudentOrm)
        editor.create_model(CourseOrm)

    try:
        yield
    finally:
        connections.close_all()
        if DB_PATH.exists():
            DB_PATH.unlink()


@pytest.fixture
def seeded_db(django_schema):
    StudentOrm.objects.all().delete()
    CourseOrm.objects.all().delete()
    SchoolOrm.objects.all().delete()

    school_a = SchoolOrm.objects.create(id=1, name="School-A", deleted=False)
    school_b = SchoolOrm.objects.create(id=2, name="School-B", deleted=False)

    alice = StudentOrm.objects.create(id=1, name="Alice", school=school_a, deleted=False)
    bob = StudentOrm.objects.create(id=2, name="Bob", school=school_a, deleted=False)
    StudentOrm.objects.create(id=3, name="Cathy", school=school_b, deleted=False)

    math = CourseOrm.objects.create(id=10, title="Math", deleted=False)
    science = CourseOrm.objects.create(id=20, title="Science", deleted=False)
    CourseOrm.objects.create(id=30, title="History", deleted=False)

    alice.courses.add(math, science)
    bob.courses.add(science)


@pytest.fixture
def orm_mappings() -> list[tuple[type[BaseModel], type]]:
    return [
        (StudentDTO, StudentOrm),
        (SchoolDTO, SchoolOrm),
        (CourseDTO, CourseOrm),
    ]
