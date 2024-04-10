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
    assert b.name == 'kikodo'
    assert b.child.pname == 'kikodo'
    assert b.child.pname2 == 'kikodo'


class Tree(BaseModel):
    name: str
    children: List[Tree] = []

    path: str = ''
    def resolve_path(self, parent):
        if parent is not None:
            return f'{parent.path}/{self.name}'
        return self.name

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
