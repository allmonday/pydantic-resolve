"""Sprint domain — independent business methods."""
from sqlalchemy import select

from src.db import session_factory
from src.models import SprintOrm


async def list_sprints() -> list[SprintOrm]:
    """获取所有 Sprint。"""
    async with session_factory() as session:
        result = await session.execute(select(SprintOrm).order_by(SprintOrm.id))
        return list(result.scalars().all())


async def get_sprint(sprint_id: int) -> SprintOrm | None:
    """获取单个 Sprint。"""
    async with session_factory() as session:
        return await session.get(SprintOrm, sprint_id)


async def create_sprint(name: str) -> SprintOrm:
    """创建新 Sprint。"""
    async with session_factory() as session:
        sprint = SprintOrm(name=name)
        session.add(sprint)
        await session.commit()
        await session.refresh(sprint)
        return sprint
