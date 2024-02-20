from __future__ import annotations
import asyncio
from pydantic import BaseModel
from typing import List
from pydantic_resolve import Resolver

class Tree(BaseModel):
    count: int
    children: List[Tree] = []

    is_over_10: bool = False
    def resolve_is_over_10(self):
        return self.count > 10


tree = dict(count=10, children=[
    dict(count=9, children=[]),
    dict(count=1, children=[
        dict(count=20, children=[])
    ])
])

async def main():
    print('go')
    t = await Resolver().resolve(Tree(**tree))
    print(t)


asyncio.run(main())