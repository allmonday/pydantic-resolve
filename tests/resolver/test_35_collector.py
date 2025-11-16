from __future__ import annotations
from pydantic import BaseModel
from typing import List
from pydantic_resolve import Resolver, Collector, LoaderDepend
import pytest


class SubCollector(Collector):
    def add(self, val):  # replace with your implementation
        print('add')
        self.val.append(val)

async def c_loader_fn(keys):
    return [[C(detail=f'{k}-1'), C(detail=f'{k}-2')] for k in keys]

class A(BaseModel):
    b_list: List[B] = []
    async def resolve_b_list(self):
        return [dict(name='b1'), dict(name='b2')]

    names: List[str] = []
    def post_names(self, collector=SubCollector('b_name')):
        return collector.values()

    items: List[str] = []
    def post_items(self, collector=Collector('b_items', flat=True)):
        return collector.values()

    details: List[str] = []
    def post_details(self, collector=Collector('c_details', flat=True)):
        return collector.values()

    details_nest: List[List[str]] = []
    def post_details_nest(self, 
                          collector=Collector('c_details')):
        return collector.values()

    details_compare: bool = False
    def post_details_compare(self, 
                          collector=Collector('c_details'),
                          collector2=Collector('c_details'),
                          ):
        return collector.values() == collector2.values()

class B(BaseModel):
    __pydantic_resolve_collect__ = {
        'name': 'b_name',
        'items': 'b_items'
    }
    name: str
    items: List[str] = ['x', 'y']

    details: List[str] = []
    def post_details(self, collector=Collector('c_details', flat=True)):
        return collector.values()

    c_list: List[C] = []
    async def resolve_c_list(self, loader=LoaderDepend(c_loader_fn)):
        return loader.load(self.name)

class C(BaseModel):
    __pydantic_resolve_collect__ = {
        'details': 'c_details'
    }
    detail: str

    details: List[str] = []
    def resolve_details(self):
        return [f'{self.detail}-detail-1', f'{self.detail}-detail-2']


@pytest.mark.asyncio
async def test_collector_1():
    a = A()
    a = await Resolver().resolve(a)
    assert a.names == ['b1', 'b2']
    assert a.items == ['x', 'y', 'x', 'y']
    assert a.details == ['b1-1-detail-1', 'b1-1-detail-2', 'b1-2-detail-1', 'b1-2-detail-2', 'b2-1-detail-1', 'b2-1-detail-2', 'b2-2-detail-1', 'b2-2-detail-2']
    assert a.details_nest == [['b1-1-detail-1', 'b1-1-detail-2'],
                              ['b1-2-detail-1', 'b1-2-detail-2'], 
                              ['b2-1-detail-1', 'b2-1-detail-2'], 
                              ['b2-2-detail-1', 'b2-2-detail-2']]

    assert a.details_compare is True