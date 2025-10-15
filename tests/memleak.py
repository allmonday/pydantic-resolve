import contextvars
import asyncio
import tracemalloc
from pydantic import BaseModel
from pydantic_resolve import Resolver

class Model(BaseModel):
    id: int

    compound_id: str = ''
    def post_compound_id(self, parent, ancestor_context):
        return f'{parent.id}-{self.id}-{ancestor_context.get("parent_id")}'

class Parent(BaseModel):
    __pydantic_resolve_expose__ = {'id': 'parent_id'}
    id: int
    m: Model
    


class Demo:
    def __init__(self):
        self.vars = contextvars.ContextVar("demo_var")

    def do(self):
        token = self.vars.set([1,2,3,4,5,6,7,8,9,10])
        self.vars.reset(token)
    

async def test_memleak():
    tracemalloc.start()
    snapshot1 = tracemalloc.take_snapshot()

    for _ in range(10000):
        await Resolver().resolve(Parent(id=1, m=Model(id=2)))
        # Demo().do()

    snapshot2 = tracemalloc.take_snapshot()
    top_stats = snapshot2.compare_to(snapshot1, 'lineno')

    print("[ Top 10 differences ]")
    for stat in top_stats[:10]:
        print(stat)

    tracemalloc.stop()


asyncio.run(test_memleak())
