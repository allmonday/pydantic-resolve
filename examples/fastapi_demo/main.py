from fastapi import FastAPI, Depends, Query
import fastapi_demo.schema as sc
import fastapi_demo.db as db
import fastapi_demo.model as md
import fastapi_demo.loader as ld
import fastapi_demo.schema as sc 
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic_resolve import Resolver

app = FastAPI(debug=True)


@app.on_event("startup")
async def startup():
    print('start')
    await db.init()
    await db.insert_objects()
    await db.insert_new_objects()
    print('done')

@app.on_event("shutdown")
async def shutdown():
    print('end start')
    await db.engine.dispose()
    print('end done')

@app.get('/tasks', response_model=List[sc.TaskSchema])
async def get_tasks(private:bool= Query(default=True),
                    session: AsyncSession = Depends(db.get_session)):
    tasks = (await session.execute(select(md.Task))).scalars().all()
    task_objs = [sc.TaskSchema.from_orm(t) for t in tasks]
    resolver = Resolver(loader_filters={ld.FeedbackLoader: {'private': private}}, ensure_type=True)
    results = await resolver.resolve(task_objs)
    return results