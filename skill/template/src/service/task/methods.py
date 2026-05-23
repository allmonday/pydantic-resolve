"""Task domain — independent business methods."""
from sqlalchemy import select

from src.db import session_factory
from src.models import TaskOrm


async def list_tasks() -> list[TaskOrm]:
    """获取所有任务。"""
    async with session_factory() as session:
        result = await session.execute(select(TaskOrm).order_by(TaskOrm.id))
        return list(result.scalars().all())


async def get_tasks_by_sprint(sprint_id: int) -> list[TaskOrm]:
    """获取指定 Sprint 下的所有任务。"""
    async with session_factory() as session:
        result = await session.execute(
            select(TaskOrm).where(TaskOrm.sprint_id == sprint_id).order_by(TaskOrm.id)
        )
        return list(result.scalars().all())


async def get_task(task_id: int) -> TaskOrm | None:
    """获取单个任务。"""
    async with session_factory() as session:
        return await session.get(TaskOrm, task_id)


async def create_task(
    title: str, sprint_id: int, owner_id: int | None = None
) -> TaskOrm:
    """在指定 Sprint 中创建新任务。"""
    async with session_factory() as session:
        task = TaskOrm(title=title, sprint_id=sprint_id, owner_id=owner_id)
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task
