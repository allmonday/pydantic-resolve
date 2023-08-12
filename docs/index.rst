Pydantic-resolve 使用手册  / Manual
====

Pydantic-resolve 是一个轻量级的工具库， 用来构建多层嵌套结构的数据。

它能通过上层的数据字段获取并关联下层的数据。 也能在获取数据之后执行post方法进行额外计算。

安装
----

.. code-block:: shell

   pip install pydantic-resolve
   

source: https://github.com/allmonday/pydantic-resolve


我们用FastAPI应用场景来举例， Tasks 接口
----

这个场景的目的是生成一个 task -> comment -> feedback 的三层嵌套数据

假设我们现在有一个API接口， get_tasks

.. code-block:: python
   :linenos:
   :emphasize-lines: 17

   class Task(Base):
      __tablename__ = "task"

      id: Mapped[int] = mapped_column(primary_key=True)
      name: Mapped[str]

   class TaskSchema(BaseModel):
      id: int
      name: str

      class Config:
         orm_mode = True

   @app.get('/tasks', response_model=List[TaskSchema])
   async def get_tasks(private:bool= Query(default=True),
                     session: AsyncSession = Depends(db.get_session)):
      tasks = (await session.execute(select(md.Task))).scalars().all()
      return tasks
   
输出：
   
.. code-block:: json

   [
      { "id": 1, "name": "setup test environment" },
      { "id": 2, "name": "initial project" },
   ]
      
通过task_id查找 task 关联的 comments
----

现在我们需要为每个task 对象关联一些comments, 操作步骤

1. 添加 dataloader, 传入需要task ids, 返回每个task id 关联的comments
2. 在Task类型上添加 comments: List[Comment] = []
3. 使用Resolver执行解析

.. code-block:: python
   :linenos:
   :emphasize-lines: 1-5, 32-34, 43

   async def comment_batch_load_fn(task_ids):
      async with db.async_session() as session:
            res = await session.execute(select(Comment).where(Comment.task_id.in_(task_ids)))
            rows = res.scalars().all()
            return build_list(rows, task_ids, lambda x: x.task_id)

   class Comment(Base):
      __tablename__ = "comment"

      id: Mapped[int] = mapped_column(primary_key=True)
      task_id: Mapped[int] = mapped_column()
      content: Mapped[str]

   class Task(Base):
      __tablename__ = "task"

      id: Mapped[int] = mapped_column(primary_key=True)
      name: Mapped[str]

   class CommentSchema(BaseModel):
      id: int
      task_id: int
      content: str

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
      tasks = await Resolver().resolve(tasks)
      return tasks

输出：
   
.. code-block:: json

   [
      { "id": 1, "name": "setup test environment", "comments": [
         { "id": 1, "task_id": 1, "content": "remember to config pipeline" },
         { "id": 2, "task_id": 1, "content": "DBA is OOO" },
      ] },
      { "id": 2, "name": "initial project", "comments": [
         { "id": 3, "task_id": 2, "content": "I need authority" },
      ] },
   ]

通过 comment_id 为 comment 添加关联的 feedback
----

我们照着这个模式，继续为每个comment对象关联一些 feedbacks.

1. 添加 dataloader, 传入需要comment ids, 返回每个comment id 关联的 feedbacks
2. 在 Comment类型上添加 feedbacks: List[Feedback] = []

.. code-block:: python
   :linenos:
   :emphasize-lines: 7-12, 46-48

   async def comment_batch_load_fn(task_ids):
      async with db.async_session() as session:
            res = await session.execute(select(Comment).where(Comment.task_id.in_(task_ids)))
            rows = res.scalars().all()
            return build_list(rows, task_ids, lambda x: x.task_id)

   async def feedback_batch_load_fn(comment_ids):
       async with db.async_session() as session:
            res = await session.execute(select(Feedback)
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

   class Feedback(Base):
      __tablename__ = "feedback"

      id: Mapped[int] = mapped_column(primary_key=True)
      comment_id: Mapped[int] = mapped_column()
      content: Mapped[str]

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
      tasks = await Resolver().resolve(tasks)
      return tasks

输出：
   
.. code-block:: json

   [
      { "id": 1, "name": "setup test environment", "comments": [
         { "id": 1, "task_id": 1, "content": "remember to config pipeline", "feedbacks": [
            { "id": 1, "comment_id": 1, "content": "roger"},
            { "id": 2, "comment_id": 1, "content": "done"},
         ] },
         { "id": 2, "task_id": 1, "content": "DBA is OOO", "feedbacks": [] },
      ] },
      { "id": 2, "name": "initial project", "comments": [
         { "id": 3, "task_id": 2, "content": "I need authority", "feedbacks": [
            { "id": 3, "comment_id": 3, "content": "received"},
            { "id": 4, "comment_id": 3, "content": "granted"},
         ] },
      ] },
   ]

.. attention:: 

   从代码上我们能看到，所有的额外关联，都没有对代码的侵入和改动。


其他使用方法：
====

* :ref:`composer`
* :ref:`context`



更多：
====

* :ref:`search`
.. * :ref:`changelog`

