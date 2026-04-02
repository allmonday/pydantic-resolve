from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import pytest
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


student_course = Table(
    "student_course",
    Base.metadata,
    Column("student_id", ForeignKey("student.id"), primary_key=True),
    Column("course_id", ForeignKey("course.id"), primary_key=True),
)


class SchoolOrm(Base):
    __tablename__ = "school"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    students: Mapped[list["StudentOrm"]] = relationship(back_populates="school")


class StudentOrm(Base):
    __tablename__ = "student"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    school_id: Mapped[int] = mapped_column(ForeignKey("school.id"))

    school: Mapped[SchoolOrm] = relationship(back_populates="students")
    courses: Mapped[list["CourseOrm"]] = relationship(
        secondary=student_course,
        back_populates="students",
    )


class CourseOrm(Base):
    __tablename__ = "course"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    students: Mapped[list[StudentOrm]] = relationship(
        secondary=student_course,
        back_populates="courses",
    )


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
async def session_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield async_session
    finally:
        await engine.dispose()


@pytest.fixture
def session_factory(
    session_maker: async_sessionmaker[AsyncSession],
) -> Callable[[], AsyncSession]:
    def _factory() -> AsyncSession:
        return session_maker()

    return _factory


@pytest.fixture
async def seeded_db(session_maker: async_sessionmaker[AsyncSession]) -> None:
    async with session_maker() as session:
        async with session.begin():
            session.add_all(
                [
                    SchoolOrm(id=1, name="School-A"),
                    SchoolOrm(id=2, name="School-B"),
                    StudentOrm(id=1, name="Alice", school_id=1),
                    StudentOrm(id=2, name="Bob", school_id=1),
                    StudentOrm(id=3, name="Cathy", school_id=2),
                    CourseOrm(id=10, title="Math"),
                    CourseOrm(id=20, title="Science"),
                    CourseOrm(id=30, title="History"),
                ]
            )
            await session.execute(
                student_course.insert(),
                [
                    {"student_id": 1, "course_id": 10},
                    {"student_id": 1, "course_id": 20},
                    {"student_id": 2, "course_id": 20},
                ],
            )


@pytest.fixture
def orm_mappings() -> list[tuple[type[BaseModel], type[Base]]]:
    return [
        (StudentDTO, StudentOrm),
        (SchoolDTO, SchoolOrm),
        (CourseDTO, CourseOrm),
    ]
