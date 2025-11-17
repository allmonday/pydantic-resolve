from uuid import uuid1
from pydantic_resolve import Resolver
import gc
from pydantic import BaseModel
import psutil
import pytest


class Model(BaseModel):
    id: int

    compound_id: str = ''
    def post_compound_id(self, parent, ancestor_context):
        return f'{parent.id}-{self.id}-{ancestor_context.get("parent_id")}'

class Parent(BaseModel):
    __pydantic_resolve_expose__ = {'id': 'parent_id'}
    id: int
    m: Model
    


def str_uuid1():
    return str(uuid1())

@pytest.mark.asyncio
async def test_mem_leak_2():
    process = psutil.Process()
    gc.collect()

    memory_start = process.memory_info().rss
    for _ in range(10000):
        await Resolver().resolve(Parent(id=1, m=Model(id=2)))

    memory_after_del = process.memory_info().rss
    diff = memory_after_del - memory_start
    print(memory_after_del, memory_start, diff/1024)
    assert diff/1024 < 500  # less than 500KB increase