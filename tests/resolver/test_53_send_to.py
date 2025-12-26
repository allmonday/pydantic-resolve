from __future__ import annotations
from pydantic import BaseModel
from typing import List, Annotated
from pydantic_resolve import Resolver, Collector, LoaderDepend, SendTo, DefineSubset, SubsetConfig
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
    name: Annotated[str, SendTo('b_name')] = ''
    items: Annotated[List[str], SendTo('b_items')] = ['x', 'y']

    details: List[str] = []
    def post_details(self, collector=Collector('c_details', flat=True)):
        return collector.values()

    c_list: List[C] = []
    async def resolve_c_list(self, loader=LoaderDepend(c_loader_fn)):
        return loader.load(self.name)

class C(BaseModel):
    detail: str

    details: Annotated[List[str], SendTo('c_details')] = []
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


class X(BaseModel):
    items: list[Y]
    sum: int = 0
    def post_sum(self, collector=Collector('collector')):
        s = 0
        for a, b in collector.values():
            s += (a + b)
        return s


class Y(BaseModel):
    a: Annotated[int, SendTo('collector')]
    b: Annotated[int, SendTo('collector')]

@pytest.mark.asyncio
async def test_collector_2():
    x = X(items=[Y(a=1, b=2), Y(a=3, b=4)])
    x = await Resolver().resolve(x)
    assert x.sum == 10


class U(BaseModel):
    items: list[V]
    sum: int = 0
    def post_sum(self, collector=Collector('collector1')):
        s = 0
        for a, b in collector.values():
            s += (a + b)
        return s

    sum2: int = 0
    def post_sum2(self, collector=Collector('collector2')):
        s = 0
        for a, b in collector.values():
            s += (a + b)
        return s


class V(BaseModel):
    a: Annotated[int, SendTo(('collector1', 'collector2'))]
    b: Annotated[int, SendTo(('collector1', 'collector2'))]

@pytest.mark.asyncio
async def test_collector_3():
    x = U(items=[V(a=1, b=2), V(a=3, b=4)])
    x = await Resolver().resolve(x)
    assert x.sum == 10
    assert x.sum2 == 10


class E(BaseModel):
    items: list[F]
    sum: int = 0
    def post_sum(self, collector=Collector('collector1')):
        s = 0
        for a, b in collector.values():
            s += (a + b)
        return s

class FBase(BaseModel):
    a: int
    b: int

class F(DefineSubset):
    __subset__ = SubsetConfig(
        kls=FBase,
        fields=['a', 'b'],
        send_to=[('a', 'collector1'), ('b', 'collector1')]
    )

@pytest.mark.asyncio
async def test_collector_with_subclass():
    e = E(items=[F(a=1, b=2), F(a=3, b=4)])
    e = await Resolver().resolve(e) 
    assert e.sum == 10
