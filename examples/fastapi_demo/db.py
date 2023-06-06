from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from fastapi_demo.model import Base, Task, Comment, Feedback

engine = create_async_engine(
    "sqlite+aiosqlite://",
    echo=False,
)

async_session = async_sessionmaker(engine, expire_on_commit=False)

async def get_session():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def insert_objects() -> None:
    async with async_session() as session:
        async with session.begin():
            session.add_all(
                [
                    Task(id=1, name="task-1"),
                    Task(id=2, name="task-2"),
                    Comment(id=1, task_id=1, content="comment-1 for task 1"),
                    Comment(id=2, task_id=2, content="comment-2 for task 2"),
                    Feedback(id=1, comment_id=1, content="feedback-1 for comment-1 (private)", private=True),
                    Feedback(id=2, comment_id=1, content="feedback-2 for comment-1 (private)", private=True),
                    Feedback(id=3, comment_id=1, content="feedback-3 for comment-1 (public)", private=False),
                    Feedback(id=4, comment_id=2, content="feedback-1 for comment-2 (public)", private=False),
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
                    Comment(id=3, task_id=1, content="comment-2 for task 1"),
                    Feedback(id=5, comment_id=2, content="feedback-2 for comment-2 (public)", private=False),
                ]
            )