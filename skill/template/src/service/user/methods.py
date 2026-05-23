"""User domain — independent business methods."""
from sqlalchemy import select

from src.db import session_factory
from src.models import UserOrm


async def list_users() -> list[UserOrm]:
    """获取所有用户。"""
    async with session_factory() as session:
        result = await session.execute(select(UserOrm).order_by(UserOrm.id))
        return list(result.scalars().all())


async def create_user(name: str) -> UserOrm:
    """创建新用户。"""
    async with session_factory() as session:
        user = UserOrm(name=name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
