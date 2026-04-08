"""Verify that build_relationship works with ORM relationships that have no DB FK constraint.

Scenario: Employee.dept_code matches Department.code via relationship(primaryjoin=...),
but there is no ForeignKey() constraint on dept_code and Department.code is not a primary key.
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Annotated, Optional

import pytest
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from pydantic_resolve import ErDiagram, config_resolver
from pydantic_resolve.integration.sqlalchemy import build_relationship
from pydantic_resolve.integration.mapping import Mapping


# --- ORM Models (no DB FK constraints) ---


class _Base(DeclarativeBase):
    pass


class DepartmentOrm(_Base):
    __tablename__ = "department_nofk"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)


class EmployeeOrm(_Base):
    __tablename__ = "employee_nofk"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    dept_code: Mapped[str] = mapped_column(String)  # No ForeignKey!

    department: Mapped[Optional[DepartmentOrm]] = relationship(
        primaryjoin="foreign(EmployeeOrm.dept_code) == DepartmentOrm.code",
    )


# --- DTOs ---


class DepartmentDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str


class EmployeeDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    dept_code: str


# --- Fixtures ---


@pytest.fixture
async def nofk_session_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)

    try:
        yield async_session
    finally:
        await engine.dispose()


@pytest.fixture
def nofk_session_factory(
    nofk_session_maker: async_sessionmaker[AsyncSession],
) -> Callable[[], AsyncSession]:
    def _factory() -> AsyncSession:
        return nofk_session_maker()

    return _factory


@pytest.fixture
async def nofk_seeded_db(nofk_session_maker: async_sessionmaker[AsyncSession]) -> None:
    async with nofk_session_maker() as session:
        async with session.begin():
            session.add_all(
                [
                    DepartmentOrm(id=1, code="ENG", name="Engineering"),
                    DepartmentOrm(id=2, code="HR", name="Human Resources"),
                    EmployeeOrm(id=1, name="Alice", dept_code="ENG"),
                    EmployeeOrm(id=2, name="Bob", dept_code="HR"),
                    EmployeeOrm(id=3, name="Carol", dept_code="ENG"),
                    EmployeeOrm(id=4, name="Dan", dept_code="MKT"),  # no matching dept
                ]
            )


# --- Tests ---


def test_build_relationship_works_without_db_fk(
    nofk_session_factory,
    nofk_seeded_db,
):
    entities = build_relationship(
        mappings=[
            Mapping(entity=EmployeeDTO, orm=EmployeeOrm),
            Mapping(entity=DepartmentDTO, orm=DepartmentOrm),
        ],
        session_factory=nofk_session_factory,
    )

    # Should produce at least one entity with relationships
    assert len(entities) > 0

    # EmployeeDTO should have a 'department' relationship
    emp_entity = next(e for e in entities if e.kls is EmployeeDTO)
    rel_names = {r.name for r in emp_entity.relationships}
    assert "department" in rel_names

    # Verify the relationship details
    dept_rel = next(r for r in emp_entity.relationships if r.name == "department")
    assert dept_rel.fk == "dept_code"


@pytest.mark.asyncio
async def test_resolver_loads_data_without_db_fk(
    nofk_session_factory,
    nofk_session_maker,
    nofk_seeded_db,
):
    entities = build_relationship(
        mappings=[
            Mapping(entity=EmployeeDTO, orm=EmployeeOrm),
            Mapping(entity=DepartmentDTO, orm=DepartmentOrm),
        ],
        session_factory=nofk_session_factory,
    )

    diagram = ErDiagram(entities=[]).add_relationship(entities)
    AutoLoad = diagram.create_auto_load()

    class EmployeeView(EmployeeDTO):
        model_config = ConfigDict(from_attributes=True)

        department: Annotated[Optional[DepartmentDTO], AutoLoad()] = None

    MyResolver = config_resolver("SA_NoDbFkResolver", er_diagram=diagram)

    async with nofk_session_maker() as session:
        employees = (
            await session.execute(select(EmployeeOrm).order_by(EmployeeOrm.id))
        ).scalars().all()

    payload = [
        EmployeeView(id=e.id, name=e.name, dept_code=e.dept_code)
        for e in employees
    ]
    result = await MyResolver().resolve(payload)

    alice = next(r for r in result if r.id == 1)
    bob = next(r for r in result if r.id == 2)
    carol = next(r for r in result if r.id == 3)
    dan = next(r for r in result if r.id == 4)

    assert alice.department == DepartmentDTO(id=1, code="ENG", name="Engineering")
    assert bob.department == DepartmentDTO(id=2, code="HR", name="Human Resources")
    assert carol.department == DepartmentDTO(id=1, code="ENG", name="Engineering")
    assert dan.department is None  # dept_code="MKT" has no match
