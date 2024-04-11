from __future__ import annotations
import pytest
from typing import Optional, List
from pydantic import BaseModel
from pydantic_resolve import Resolver


class Base(BaseModel):
    name: str

    child: Optional[Child] = None
    def resolve_child(self):
        return Child()

    children: List[Child] = []
    def resolve_children(self):
        return [Child()]
    
    parent: Optional[str] = '123'
    def resolve_parent(self, parent):
        return parent

class Child(BaseModel):
    pname: str = ''
    def resolve_pname(self, parent: Base):
        return parent.name
    
    pname2: str = ''
    def resolve_pname2(self, parent: Base):
        return parent.name


@pytest.mark.asyncio
async def test_parent():
    b = Base(name='kikodo')
    b = await Resolver().resolve(b)
    assert b.parent is None  # parent of root is none

    assert b.name == 'kikodo'
    assert b.child.pname == 'kikodo'
    assert b.child.pname2 == 'kikodo'  # work with obj

    assert b.children[0].pname == 'kikodo'
    assert b.children[0].pname2 == 'kikodo'  # work with list


class Tree(BaseModel):
    name: str

    path: str = ''
    def resolve_path(self, parent):
        if parent is not None:
            return f'{parent.path}/{self.name}'
        return self.name
    children: List[Tree] = []

@pytest.mark.asyncio
async def test_tree():
    data = dict(name="a", children=[
        dict(name="b", children=[
            dict(name="c")
        ]),
        dict(name="d", children=[
            dict(name="c")
        ])
    ]) 
    data = await Resolver().resolve(Tree(**data))
    assert data.dict() ==  dict(name="a", path="a", children=[
        dict(name="b", path="a/b", children=[
            dict(name="c", path="a/b/c", children=[])
        ]),
        dict(name="d", path="a/d", children=[
            dict(name="c", path="a/d/c", children=[])
        ])
    ]) 
    print(data.json(indent=2))
