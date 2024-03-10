.. _filter:

3. 通过 loader_filters 改变loader 查询条件 
====

存在一种情况， 我们希望dataloader 中可以添加一些额外的过滤条件，比如我们希望过滤掉标记为deleted 的 comments 和 feedbacks.
或者在某些情况下，查找标为deleted的记录

dataloader filter 参数可以做到

.. code-block:: python
   :linenos:
   :emphasize-lines: 2, 6, 12, 16, 33, 41, 77-84

   class CommentLoader(DataLoader):
      deleted: bool
      async def batch_load_fn(task_ids):
         async with db.async_session() as session:
               res = await session.execute(select(Comment)
                     .where(Commend.deleted.is_(self.deleted))
                     .where(Comment.task_id.in_(task_ids)))
               rows = res.scalars().all()
               return build_list(rows, task_ids, lambda x: x.task_id)

   class FeedbackLoader(DataLoader):
      deleted: bool
      async def batch_load_fn(comment_ids):
         async with db.async_session() as session:
               res = await session.execute(select(Feedback)
                  .where(feedback.deleted.is_(self.deleted))
                  .where(Feedback.comment_id.in_(comment_ids)))
               rows = res.scalars().all()
               return build_list(rows, comment_ids, lambda x: x.comment_id)

   class Task(Base):
      __tablename__ = "task"

      id: Mapped[int] = mapped_column(primary_key=True)
      name: Mapped[str]

   class Comment(Base):
      __tablename__ = "comment"

      id: Mapped[int] = mapped_column(primary_key=True)
      task_id: Mapped[int] = mapped_column()
      content: Mapped[str]
      deleted: Mapped[bool]

   class Feedback(Base):
      __tablename__ = "feedback"

      id: Mapped[int] = mapped_column(primary_key=True)
      comment_id: Mapped[int] = mapped_column()
      content: Mapped[str]
      deleted: Mapped[bool]

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
      def resolve_feedbacks(self, feedback_loader=LoaderDepend(feedback_batch_load_fn)):
         return feedback_loader.load(self.id)

      class Config:
         orm_mode = True

   class TaskSchema(BaseModel):
      id: int
      name: str

      comments: List[CommentSchema] = [] 
      def resolve_comments(self, comment_loader=LoaderDepend(comment_batch_load_fn)):
         return comment_loader.load(self.id)

      class Config:
         orm_mode = True

   @app.get('/tasks', response_model=List[TaskSchema])
   async def get_tasks(private:bool= Query(default=True),
                     session: AsyncSession = Depends(db.get_session)):
      tasks = (await session.execute(select(Task))).scalars().all()
      loder_filters = {
         CommentLoader: {
            'deleted': False
         },
         FeedbackLoader: {
            'deleted': False
         },
      }

      tasks = await Resolver(loader_filters=loader_filters).resolve(tasks)
      return tasks
