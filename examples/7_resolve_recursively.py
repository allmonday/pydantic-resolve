from __future__ import annotations
import asyncio
from random import random
from typing import Optional
from time import time
from pydantic import BaseModel
from pydantic_resolve import resolve

t = time()

class B(BaseModel):
    node_a: Optional[A] = None
    async def resolve_value_1(self):
        print(f"resolve a, {time() - t}")
        await asyncio.sleep(1)  # sleep 1
        return A()

class A(BaseModel):
    node_b: Optional[B] = None
    async def resolve_node_b(self):
        print(f"resolve b, {time() - t}")
        await asyncio.sleep(1)
        return B()

async def main():
    a = A()
    result = await resolve(a)
    print(result.json())
    print(f'total {time() - t}')

asyncio.run(main())