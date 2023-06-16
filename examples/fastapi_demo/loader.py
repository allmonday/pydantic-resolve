from aiodataloader import DataLoader
import fastapi_demo.model as sm
import fastapi_demo.db as db
from sqlalchemy import select
from pydantic_resolve.util import build_list

class FeedbackLoader(DataLoader):
    private: bool

    async def batch_load_fn(self, comment_ids):
        async with db.async_session() as session:
            res = await session.execute(select(sm.Feedback)
                .where(sm.Feedback.private==self.private)  # <-------- global filter
                .where(sm.Feedback.comment_id.in_(comment_ids)))
            rows = res.scalars().all()
            return build_list(rows, comment_ids, lambda x: x.comment_id)

class CommentLoader(DataLoader):
    async def batch_load_fn(self, task_ids):
        async with db.async_session() as session:
            res = await session.execute(select(sm.Comment).where(sm.Comment.task_id.in_(task_ids)))
            rows = res.scalars().all()
            return build_list(rows, task_ids, lambda x: x.task_id)