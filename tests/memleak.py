import asyncio
import tracemalloc
from pydantic import BaseModel
from pydantic_resolve import Resolver

class Model(BaseModel):
    id: int


async def test_memleak():
    tracemalloc.start()
    snapshot1 = tracemalloc.take_snapshot()

    for _ in range(10000):
        await Resolver().resolve(Model(id=1))

    snapshot2 = tracemalloc.take_snapshot()
    top_stats = snapshot2.compare_to(snapshot1, 'lineno')

    print("[ Top 10 differences ]")
    for stat in top_stats[:10]:
        print(stat)

    tracemalloc.stop()


asyncio.run(test_memleak())
