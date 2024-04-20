from __future__ import annotations
import asyncio
from typing import List
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend, build_list
from aiodataloader import DataLoader



root = { 'id': 1, 'content': 'root' }
records = [
    {'id': 2, 'parent': 1, 'content': '2'},
    {'id': 3, 'parent': 1, 'content': '3'},
    {'id': 4, 'parent': 2, 'content': '4'},
    {'id': 5, 'parent': 3, 'content': '5'},
]

class Loader(DataLoader):
    records: List[dict]
    async def batch_load_fn(self, keys):
        return build_list(self.records, keys, lambda x: x['parent'])

class Tree(BaseModel):
    id: int
    content: str
    
    path: str = ''
    def resolve_path(self, parent):
        if parent:
            return f'{parent.path}/{self.content}'
        else:
            return self.content
    
    children: List[Tree] = []
    def resolve_children(self, loader=LoaderDepend(Loader)):
        return loader.load(self.id)
        
async def main():
    tree = Tree(id=1, content='root')
    tree = await Resolver(loader_params={Loader: {'records': records}}).resolve(tree)
    print(tree.json(indent=2))


asyncio.run(main())
