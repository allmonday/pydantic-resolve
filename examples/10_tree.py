from __future__ import annotations
import asyncio
from pydantic import BaseModel
from typing import List
from pydantic_resolve import Resolver

class Tree(BaseModel):
    count: int
    children: List[Tree] = []
    
    total: int = 0
    def post_total(self):
        return self.count + sum([c.total for c in self.children])


tree = dict(count=10, children=[
    dict(count=9, children=[]),
    dict(count=1, children=[
        dict(count=20, children=[])
    ])
])

async def main():
    t = await Resolver().resolve(Tree(**tree))
    print(t.json(indent=2))


asyncio.run(main())