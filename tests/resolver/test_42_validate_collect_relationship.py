from __future__ import annotations
from pydantic import BaseModel
from typing import List
from pydantic_resolve import Resolver
from pydantic_resolve.exceptions import MissingCollector
import pytest

class Root(BaseModel):
    list_a: List[A] = []
    def resolve_list_a(self):
        return data

class A(BaseModel):
    list_b: List[B]

class B(BaseModel):
    __pydantic_resolve_collect__ = {'name': 'field_name'}  # missing collector
    name: str
    list_c: List[C]

class C(BaseModel):
    __pydantic_resolve_collect__ = {'name': 'field_name'}
    name: str

data = [
        {'list_b': [
            {'name': 'b1', 'list_c': [
                {'name': 'c1'}
            ]},
            {'name': 'b2', 'list_c': []},
        ]},
        {'list_b': [
            {'name': 'b3', 'list_c': []},
            {'name': 'b4', 'list_c': [
                {'name': 'c4'}
            ]},
        ]},
    ]

@pytest.mark.asyncio
async def test_collector_1():
    root = Root()
    with pytest.raises(MissingCollector):
        await Resolver().resolve(root)