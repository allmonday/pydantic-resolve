from __future__ import annotations
import asyncio
from typing import List
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend, build_list
from aiodataloader import DataLoader



roots = [{ 'id': 1, 'content': 'root' }, {'id': 6, 'content': '6'}]
records = [
    {'id': 2, 'parent': 1, 'content': '2'},
    {'id': 3, 'parent': 1, 'content': '3'},
    {'id': 4, 'parent': 2, 'content': '4'},
    {'id': 5, 'parent': 3, 'content': '5'},
    {'id': 7, 'parent': 6, 'content': '7'},
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
    import json
    trees = [Tree(id=1, content='root')]
    trees = await Resolver(loader_params={Loader: {'records': records}}).resolve(trees)
    trees = [t.dict() for t in trees]
    print(json.dumps(trees, indent=2))

asyncio.run(main())
