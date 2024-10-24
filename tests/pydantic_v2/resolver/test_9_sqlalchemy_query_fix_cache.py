from typing import List
import pytest
from collections import Counter, defaultdict
from typing import Tuple
from aiodataloader import DataLoader
from pydantic import ConfigDict, BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from pydantic_resolve import Resolver, LoaderDepend

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

@pytest.mark.asyncio
async def test_sqlite_and_dataloader():
    counter = Counter()
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        echo=False,
    )
    async_session = async_sessionmaker(engine, expire_on_commit=False)

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

    class FeedbackLoader(DataLoader):
        async def batch_load_fn(self, comment_ids):
            counter['load-feedback'] += 1
            async with async_session() as session:
                res = await session.execute(select(Feedback).where(Feedback.comment_id.in_(comment_ids)))
                rows = res.scalars().all()
                dct = defaultdict(list)
                for row in rows:
                    dct[row.comment_id].append(FeedbackSchema.model_validate(row))
                return [dct.get(k, []) for k in comment_ids]

    class CommentLoader(DataLoader):
        async def batch_load_fn(self, task_ids):
            counter['load-comment'] += 1
            async with async_session() as session:
                res = await session.execute(select(Comment).where(Comment.task_id.in_(task_ids)))
                rows = res.scalars().all()

                dct = defaultdict(list)
                for row in rows:
                    dct[row.task_id].append(CommentSchema.model_validate(row))
                return [dct.get(k, []) for k in task_ids]

    class FeedbackSchema(BaseModel):
        id: int
        comment_id: int
        content: str
        model_config = ConfigDict(from_attributes=True)

    class CommentSchema(BaseModel):
        id: int
        task_id: int
        content: str
        feedbacks: List[FeedbackSchema]  = []

        def resolve_feedbacks(self, loader=LoaderDepend(FeedbackLoader)):
            return loader.load(self.id)
        model_config = ConfigDict(from_attributes=True)

    class TaskSchema(BaseModel):
        id: int
        name: str
        comments: List[CommentSchema]  = []
        
        def resolve_comments(self, loader=LoaderDepend(CommentLoader)):
            return loader.load(self.id)
        model_config = ConfigDict(from_attributes=True)

    async def init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def query():
        async with async_session() as session:
            tasks = (await session.execute(select(Task))).scalars().all()
            task_objs = [TaskSchema.model_validate(t) for t in tasks]
            resolved_results = await Resolver().resolve(task_objs)
            to_dict_arr = [r.model_dump() for r in resolved_results]
            return to_dict_arr

    await init()
    await insert_objects()
    result = await query()
    expected = [
        {
            'comments': [{'content': 'comment-1 for task 1',
            'feedbacks': [{'comment_id': 1,
                            'content': 'feedback-1 for comment-1',
                            'id': 1},
                            {'comment_id': 1,
                            'content': 'feedback-1 for comment-1',
                            'id': 2},
                            {'comment_id': 1,
                            'content': 'feedback-1 for comment-1',
                            'id': 3}],
            'id': 1,
            'task_id': 1},
                        {'content': 'comment-2 for task 1',
                            'feedbacks': [],
                            'id': 2,
                            'task_id': 1}],
            'id': 1,
            'name': 'task-1'},
            {'comments': [{'content': 'comment-1 for task 2',
                            'feedbacks': [],
                            'id': 3,
                            'task_id': 2}],
            'id': 2,
            'name': 'task-2'},
            {'comments': [], 'id': 3, 'name': 'task-3'}]

    assert result == expected
    assert counter['load-comment'] == 1  # batch_load_fn only called once
    assert counter['load-feedback'] == 1
    
    await query()

    assert counter['load-comment'] == 2  # Resolver + LoaderDepend can fix cache issue
    assert counter['load-feedback'] == 2