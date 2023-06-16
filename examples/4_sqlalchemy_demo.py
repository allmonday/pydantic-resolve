from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import List
from aiodataloader import DataLoader
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from pydantic_resolve import resolve, mapper, build_list
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

async def insert_objects() -> None:
    async with async_session() as session:
        async with session.begin():
            session.add_all(
                [
                    Task(id=1, name="task-1"),
                    Task(id=2, name="task-2"),
                    Task(id=3, name="task-3"),

                    Comment(id=1, task_id=1, content="comment-1 for task 1"),
                    Comment(id=2, task_id=1, content="comment-2 for task 1"),
                    Comment(id=3, task_id=2, content="comment-1 for task 2"),

                    Feedback(id=1, comment_id=1, content="feedback-1 for comment-1"),
                    Feedback(id=2, comment_id=1, content="feedback-1 for comment-1"),
                    Feedback(id=3, comment_id=1, content="feedback-1 for comment-1"),
                ]
            )

# =========================== Pydantic Schema layer =========================
class FeedbackLoader(DataLoader):
    async def batch_load_fn(self, comment_ids):
        async with async_session() as session:
            res = await session.execute(select(Feedback).where(Feedback.comment_id.in_(comment_ids)))
            rows = res.scalars().all()
            return build_list(rows, comment_ids, lambda x: x.comment_id)


class CommentLoader(DataLoader):
    async def batch_load_fn(self, task_ids):
        async with async_session() as session:
            res = await session.execute(select(Comment).where(Comment.task_id.in_(task_ids)))
            rows = res.scalars().all()
            return build_list(rows, task_ids, lambda x: x.task_id)

feedback_loader = FeedbackLoader()
comment_loader = CommentLoader()

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
    feedbacks: List[FeedbackSchema] = []

    @mapper(lambda items: [FeedbackSchema.from_orm(i) for i in items])
    def resolve_feedbacks(self):
        return feedback_loader.load(self.id)

    class Config:
        orm_mode = True

class TaskSchema(BaseModel):
    id: int
    name: str
    comments: List[CommentSchema]  = []
    
    @mapper(lambda items: [CommentSchema.from_orm(i) for i in items])
    def resolve_comments(self):
        return comment_loader.load(self.id)

    class Config:
        orm_mode = True

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await insert_objects()

    async with async_session() as session:
        tasks = (await session.execute(select(Task))).scalars().all()
        task_objs = [TaskSchema.from_orm(t) for t in tasks]
        resolved_results = await resolve(task_objs)
        to_dict_arr = [r.dict() for r in resolved_results]
        pprint(to_dict_arr)

    await engine.dispose()

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
loop.close()