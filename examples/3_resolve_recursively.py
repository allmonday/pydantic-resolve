import asyncio
from random import random
from typing import Optional
from time import time
from pydantic import BaseModel
from pydantic_resolve import Resolver

t = time()

class B(BaseModel):  # recursively, concurrently resolve fields
    value_1: int = 0
    async def resolve_value_1(self):
        print(f"resolve_value_1, {time() - t}")
        await asyncio.sleep(1)  # sleep 1
        return random()

    value_2: int = 0
    async def resolve_value_2(self):
        print(f"resolve_value_1, {time() - t}")
        await asyncio.sleep(1)  # sleep 1
        return random()

class A(BaseModel):
    node_b_1: Optional[B] = None
    async def resolve_node_b_1(self):
        print(f"resolve_node_b_1, {time() - t}")
        await asyncio.sleep(1)
        return B()

    node_b_2: Optional[B] = None
    async def resolve_node_b_2(self):
        print(f"resolve_node_b_1, {time() - t}")
        await asyncio.sleep(1)
        return B()

class Root(BaseModel):
    node_a_1: Optional[A] = None
    async def resolve_node_a_1(self):
        print(f"resolve_node_a_1, {time() - t}")
        await asyncio.sleep(1)
        return A()

    node_a_2: Optional[A] = None
    async def resolve_node_a_2(self):
        print(f"resolve_node_a_2, {time() - t}")
        await asyncio.sleep(1)
        return A()

async def main():
    from pprint import pprint
    root = Root()
    result = await Resolver().resolve(root)
    pprint(result.json())
    print(f'total {time() - t}')

asyncio.run(main())