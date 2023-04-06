from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Tuple
from aiodataloader import DataLoader
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from pydantic_resolve import Resolver, LoaderDepend
from pprint import pprint

engine = create_async_engine(
    "sqlite+aiosqlite://",
    echo=False,
)
async_session = async_sessionmaker(engine, expire_on_commit=False)

# =========================== ORM layer =========================
class Base(DeclarativeBase):
    pass

class Task(Base):
    __tablename__ = "task"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]

class Comment(Base):
    __tablename__ = "comment"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column()
    content: Mapped[str]

class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    comment_id: Mapped[int] = mapped_column()
    content: Mapped[str]
    private: Mapped[bool]     # <------------ global filter

async def insert_objects() -> None:
    async with async_session() as session:
        async with session.begin():
            session.add_all(
                [
                    Task(id=1, name="task-1"),

                    Comment(id=1, task_id=1, content="comment-1 for task 1"),

                    Feedback(id=1, comment_id=1, content="feedback-1 for comment-1", private=True),
                    Feedback(id=2, comment_id=1, content="feedback-2 for comment-1", private=True),
                    Feedback(id=3, comment_id=1, content="feedback-3 for comment-1", private=False),
                ]
            )

async def insert_new_objects() -> None:
    async with async_session() as session:
        async with session.begin():
            task_1 = (await session.execute(select(Task).filter_by(id=1))).scalar_one()
            task_1.name = 'task-1 x'
            session.add(task_1)
            session.add_all(
                [
                    Comment(id=2, task_id=1, content="comment-2 for task 1"),
                    Feedback(id=4, comment_id=2, content="test", private=False),
                ]
            )


# =========================== Pydantic Schema layer =========================
class FeedbackLoader(DataLoader):
    private: bool
    async def batch_load_fn(self, comment_ids):
        async with async_session() as session:
            res = await session.execute(select(Feedback).where(Feedback.private==self.private).where(Feedback.comment_id.in_(comment_ids)))
            rows = res.scalars().all()
            dct = defaultdict(list)
            for row in rows:
                dct[row.comment_id].append(FeedbackSchema.from_orm(row))
            return [dct.get(k, []) for k in comment_ids]

class CommentLoader(DataLoader):
    async def batch_load_fn(self, task_ids):
        async with async_session() as session:
            res = await session.execute(select(Comment).where(Comment.task_id.in_(task_ids)))
            rows = res.scalars().all()

            dct = defaultdict(list)
            for row in rows:
                dct[row.task_id].append(CommentSchema.from_orm(row))
            return [dct.get(k, []) for k in task_ids]


class FeedbackSchema(BaseModel):
    id: int
    comment_id: int
    content: str

    class Config:
        orm_mode = True

class CommentSchema(BaseModel):
    id: int
    task_id: int
    content: str
    feedbacks: Tuple[FeedbackSchema, ...]  = tuple()

    def resolve_feedbacks(self, feedback_loader = LoaderDepend(FeedbackLoader)):
        return feedback_loader.load(self.id)

    class Config:
        orm_mode = True

class TaskSchema(BaseModel):
    id: int
    name: str
    comments: Tuple[CommentSchema, ...]  = tuple()
    
    def resolve_comments(self, comment_loader = LoaderDepend(CommentLoader)):
        return comment_loader.load(self.id)

    class Config:
        orm_mode = True

async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def query_tasks():
    print('---------------- query --------------')
    async with async_session() as session:
        tasks = (await session.execute(select(Task))).scalars().all()
        task_objs = [TaskSchema.from_orm(t) for t in tasks]
        resolver = Resolver(loader_filters={FeedbackLoader: {'private': True}})   # <----- global filter
        resolved_results = await resolver.resolve(task_objs)
        arr = [r.dict() for r in resolved_results]
        pprint(arr)

async def main():
    """
    almost the same with previous demo except using LoaderDepend to isolate the cache by async contextvar.
    result of first and second shall be different.
    """
    await init()
    await insert_objects()
    # first
    await query_tasks()

    # check the update and insert
    await insert_new_objects()  

    # second
    await query_tasks()
    await engine.dispose()


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
loop.close()