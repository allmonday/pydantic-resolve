"""Database engine + session factory (no model imports).

This module is safe to import from both models.py and database.py.
"""
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

engine = create_async_engine("sqlite+aiosqlite://", echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


def session_factory():
    """Session factory used by build_relationship loaders and methods."""
    return async_session_factory()
