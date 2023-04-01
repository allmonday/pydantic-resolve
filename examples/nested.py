import asyncio
from random import random
from time import time
from pydantic import BaseModel
from pydantic_resolve import resolve


class NodeB(BaseModel):  # concurrently resolve fields
    value_1: int = 0
    async def resolve_value_1(self):
        await asyncio.sleep(1)  # sleep 1
        return random()
    
    value_2: int = 0
    async def resolve_value_2(self):
        await asyncio.sleep(1)  # sleep 1
        return 12

    value_3: int = 0
    async def resolve_value_3(self):
        await asyncio.sleep(1)  # sleep 1
        return 12

class NodeA(BaseModel):
    node_b_1: int = 0
    def resolve_node_b_1(self):
        return NodeB()

    node_b_2: int = 0
    def resolve_node_b_2(self):
        return NodeB()

class Root(BaseModel):
    node_a_1: int = 0
    def resolve_node_a_1(self):
        return NodeA()

    node_a_2: int = 0
    def resolve_node_a_2(self):
        return NodeA()

async def main():
    t = time()
    root = Root()
    result = await resolve(root)
    print(result.json())
    print(time() - t)
