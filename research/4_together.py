from __future__ import annotations
import asyncio
from collections import defaultdict
from typing import List
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend
from aiodataloader import DataLoader


class DummyLoader(DataLoader):
    async def batch_load_fn(self, keys):
        return keys

loader = DummyLoader()

records = [
    {'id': 2, 'parent': 1, 'content': '2'},
    {'id': 3, 'parent': 1, 'content': '3'},
    {'id': 4, 'parent': 2, 'content': '4'},
]

d = defaultdict(list)
for r in records:
    d[r['parent']].append(r)

class Tree(BaseModel):
    id: int
    content: str
    children: List[Tree] = []
    def resolve_children(self, loader=LoaderDepend(DummyLoader)):
        return loader.load(self.id)

async def main():
    for k, v in d.items():
        loader.prime(k, v)
    tree = Tree(id=1, content='1')
    tree = await Resolver(loader_instances={DummyLoader: loader}).resolve(tree)
    print(tree.dict())

asyncio.run(main())