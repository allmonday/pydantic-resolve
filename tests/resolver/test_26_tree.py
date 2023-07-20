from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import List
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend, mapper
from aiodataloader import DataLoader
import pytest

class DummyLoader(DataLoader):
    async def batch_load_fn(self, keys):
        d = dict()
        return [d.get(k, []) for k in keys]

class Tree(BaseModel):
    id: int
    content: str
    children: List[Tree] = []
    def resolve_children(self, loader=LoaderDepend(DummyLoader)):
        return loader.load(self.id)
    
@dataclass
class DTree:
    id: int
    content: str
    children: List[DTree] = field(default_factory=list)
    def resolve_children(self, loader=LoaderDepend(DummyLoader)):
        return loader.load(self.id)

@pytest.mark.asyncio
async def test_1():

    loader = DummyLoader()

    records = [
        {'id': 2, 'parent': 1, 'content': '2'},
        {'id': 3, 'parent': 1, 'content': '3'},
        {'id': 4, 'parent': 2, 'content': '4'},
    ]

    d = defaultdict(list)
    for r in records:
        d[r['parent']].append(r)

    for k, v in d.items():
        loader.prime(k, v)

    tree = Tree(id=1, content='1')
    tree = await Resolver(loader_instances={DummyLoader: loader}).resolve(tree)
    expected = {
        'id': 1, 'content': '1', 'children': [
            {
                'id': 2, 'content': '2', 'children': [
                    { 'id': 4, 'content': '4', 'children': [] }
                ]
            },
            {'id': 3, 'content': '3', 'children': [] },
        ],
    }
    assert tree.dict() == expected


@pytest.mark.asyncio
async def test_2():

    loader = DummyLoader()

    records = [
        {'id': 2, 'parent': 1, 'content': '2'},
        {'id': 3, 'parent': 1, 'content': '3'},
        {'id': 4, 'parent': 2, 'content': '4'},
    ]

    d = defaultdict(list)
    for r in records:
        d[r['parent']].append(r)

    for k, v in d.items():
        loader.prime(k, v)

    tree = DTree(id=1, content='1')
    with pytest.raises(RecursionError):
        await Resolver(
            annotation_class=DTree,
            loader_instances={DummyLoader: loader}).resolve(tree)