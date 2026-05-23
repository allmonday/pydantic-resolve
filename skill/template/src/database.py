"""Phase 1: Database seed data.

Create tables and seed mock data for development.
"""
from sqlalchemy import select

from src.db import engine, session_factory
from src.models import SprintOrm, TaskOrm, UserOrm


async def init_db() -> None:
    """Create tables and seed mock data."""
    from src.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        result = await session.execute(select(UserOrm))
        if result.first():
            return

        users = [
            UserOrm(id=1, name="Alice"),
            UserOrm(id=2, name="Bob"),
            UserOrm(id=3, name="Charlie"),
        ]
        session.add_all(users)
        await session.flush()

        sprints = [
            SprintOrm(id=1, name="Sprint 1"),
            SprintOrm(id=2, name="Sprint 2"),
        ]
        session.add_all(sprints)
        await session.flush()

        tasks = [
            TaskOrm(id=1, title="Setup CI/CD", sprint_id=1, owner_id=1, done=True),
            TaskOrm(id=2, title="Design schema", sprint_id=1, owner_id=2, done=True),
            TaskOrm(id=3, title="Build API", sprint_id=1, owner_id=1, done=False),
            TaskOrm(id=4, title="Write tests", sprint_id=2, owner_id=3, done=False),
            TaskOrm(id=5, title="Deploy", sprint_id=2, owner_id=2, done=False),
        ]
        session.add_all(tasks)
        await session.commit()
