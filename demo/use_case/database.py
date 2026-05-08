"""Database setup — SQLAlchemy ORM models + aiosqlite in-memory + seed data.

Provides the data layer shared by RpcService classes and FastAPI endpoints.
"""

from typing import List

from sqlalchemy import ForeignKey, String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# =====================================
# Database Setup
# =====================================

engine = create_async_engine("sqlite+aiosqlite://", echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


def session_factory() -> AsyncSession:
    """Session factory used by build_relationship loaders."""
    return async_session_factory()


# =====================================
# ORM Models
# =====================================


class Base(DeclarativeBase):
    pass


class UserOrm(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)

    tasks: Mapped[List["TaskOrm"]] = relationship(back_populates="owner")


class TaskOrm(Base):
    __tablename__ = "task"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String)
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    sprint_id: Mapped[int] = mapped_column(ForeignKey("sprint.id"))

    owner: Mapped["UserOrm"] = relationship(back_populates="tasks")
    sprint: Mapped["SprintOrm"] = relationship(back_populates="tasks")


class SprintOrm(Base):
    __tablename__ = "sprint"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)

    tasks: Mapped[List["TaskOrm"]] = relationship(back_populates="sprint")


# =====================================
# Database Initialization
# =====================================


async def init_db() -> None:
    """Create tables and seed data. Must be called at app startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        async with session.begin():
            session.add_all([
                # Users
                UserOrm(id=1, name="Alice", email="alice@example.com"),
                UserOrm(id=2, name="Bob", email="bob@example.com"),
                UserOrm(id=3, name="Charlie", email="charlie@example.com"),
                # Sprints
                SprintOrm(id=1, name="Sprint 1"),
                SprintOrm(id=2, name="Sprint 2"),
                # Tasks
                TaskOrm(id=1, title="Setup project", owner_id=1, sprint_id=1),
                TaskOrm(id=2, title="Implement auth", owner_id=2, sprint_id=1),
                TaskOrm(id=3, title="Write tests", owner_id=1, sprint_id=2),
                TaskOrm(id=4, title="Deploy to prod", owner_id=3, sprint_id=2),
                TaskOrm(id=5, title="Code review", owner_id=2, sprint_id=2),
            ])
