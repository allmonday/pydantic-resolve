from collections import defaultdict
from aiodataloader import DataLoader
import fastapi_demo.schema as sc
import fastapi_demo.model as sm
import fastapi_demo.db as db
from sqlalchemy import select

class FeedbackLoader(DataLoader):
    private: bool

    async def batch_load_fn(self, comment_ids):
        async with db.async_session() as session:
            res = await session.execute(select(sm.Feedback)
                .where(sm.Feedback.private==self.private)  # <-------- global filter
                .where(sm.Feedback.comment_id.in_(comment_ids)))
            rows = res.scalars().all()
            dct = defaultdict(list)
            for row in rows:
                dct[row.comment_id].append(sc.FeedbackSchema.from_orm(row))
            return [dct.get(k, []) for k in comment_ids]

class CommentLoader(DataLoader):
    async def batch_load_fn(self, task_ids):
        async with db.async_session() as session:
            res = await session.execute(select(sm.Comment).where(sm.Comment.task_id.in_(task_ids)))
            rows = res.scalars().all()

            dct = defaultdict(list)
            for row in rows:
                dct[row.task_id].append(sc.CommentSchema.from_orm(row))
            return [dct.get(k, []) for k in task_ids]