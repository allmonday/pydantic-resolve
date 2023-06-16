from asyncio import Future
from pydantic import BaseModel
from typing import List
from pydantic_resolve import LoaderDepend, mapper
import fastapi_demo.loader as ld


class FeedbackSchema(BaseModel):
    id: int
    comment_id: int
    content: str
    private: bool

    class Config:
        orm_mode = True

class CommentSchema(BaseModel):
    id: int
    task_id: int
    content: str

    feedbacks: List[FeedbackSchema] = [] 
    @mapper(lambda items: [FeedbackSchema.from_orm(i) for i in items])
    def resolve_feedbacks(self, feedback_loader=LoaderDepend(ld.FeedbackLoader)) -> Future[List[FeedbackSchema]]:
        return feedback_loader.load(self.id)

    class Config:
        orm_mode = True

class TaskSchema(BaseModel):
    id: int
    name: str

    comments: List[CommentSchema] = [] 
    @mapper(lambda items: [CommentSchema.from_orm(i) for i in items])
    def resolve_comments(self, comment_loader=LoaderDepend(ld.CommentLoader)) -> Future[List[CommentSchema]]:
        return comment_loader.load(self.id)

    class Config:
        orm_mode = True
