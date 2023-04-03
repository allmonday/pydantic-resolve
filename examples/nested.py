import asyncio
from random import random
from time import time
from pydantic import BaseModel
from pydantic_resolve import resolve

t = time()

class NodeB(BaseModel):  # concurrently resolve fields
    value_1: int = 0
    async def resolve_value_1(self):
        print(f"resolve_value_1, {time() - t}")
        await asyncio.sleep(1)  # sleep 1
        return random()

class NodeA(BaseModel):
    node_b_1: int = 0
    async def resolve_node_b_1(self):
        print(f"resolve_node_b_1, {time() - t}")
        await asyncio.sleep(1)
        return NodeB()

class Root(BaseModel):
    node_a_1: int = 0
    async def resolve_node_a_1(self):
        print(f"resolve_node_a_1, {time() - t}")
        await asyncio.sleep(1)
        return NodeA()

    node_a_2: int = 0
    async def resolve_node_a_2(self):
        print(f"resolve_node_a_2, {time() - t}")
        await asyncio.sleep(1)
        return NodeA()

    node_a_3: int = 0
    async def resolve_node_a_3(self):
        print(f"resolve_node_a_3, {time() - t}")
        await asyncio.sleep(1)
        return NodeA()

async def main():
    root = Root()
    result = await resolve(root)
    print(result.json())
    print(f'total {time() - t}')

asyncio.run(main())