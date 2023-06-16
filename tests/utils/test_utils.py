from typing import List
from pydantic_resolve import util
from pydantic import BaseModel
import pytest
from aiodataloader import DataLoader
import asyncio

def test_get_class_field_annotations():
    class C:
        hello: str

        def __init__(self, c: str):
            self.c = c
        
    class D(C):
        pass

    class E(C):
        world: str
    
    assert list(util.get_class_field_annotations(C)) == ['hello']
    assert list(util.get_class_field_annotations(D)) == []
    assert list(util.get_class_field_annotations(E)) == ['world']


class User(BaseModel):
    id: int
    name: str
    age: int


def test_build_object():
    raw = [(1, 'peter', 10), (2, 'mike', 21), (3, 'john', 12)]
    users = [User(id=i[0], name=i[1], age=i[2]) for i in raw]
    a, b, c = users
    ids = [2, 3, 1, 4]
    output = util.build_object(users, ids, lambda x: x.id)
    assert output == [b, c, a, None]
    

def test_build_list():
    raw = [(1, 'peter', 10), (2, 'mike', 21), (3, 'john', 12)]
    users = [User(id=i[0], name=i[1], age=i[2]) for i in raw]
    a, b, c = users
    ids = [2, 3, 1, 4]
    output = util.build_list(users, ids, lambda x: x.id)
    assert output == [[b], [c], [a], []]


@pytest.mark.asyncio
async def test_transoform_decorator():

    @util.transformer_decorator(lambda x: str(x))
    async def test():
        return [1,2,3]
    
    value = await test()
    assert value == ['1', '2', '3']


@pytest.mark.asyncio
async def test_transoform_decorator_2():
    class Data(BaseModel):
        a: int

    @util.transformer_decorator(lambda x: Data(a=x['a']))
    async def test():
        return [{'a': 1}, {'a': 2}, {'a': 3}]
    
    value = await test()
    assert value == [Data(a=1), Data(a=2), Data(a=3)]

    async def test2():
        return [{'a': 1}, {'a': 2}, {'a': 3}]
    test3 = util.transformer_decorator(lambda x: Data(a=x['a']))(test2)

    value2 = await test3()
    assert value2 == [Data(a=1), Data(a=2), Data(a=3)]


@pytest.mark.asyncio
async def test_transoform_decorator_3():
    class Data(BaseModel):
        a: int

    @util.transformer_decorator(lambda x: Data(a=x))
    async def loader(keys):
        return keys
    
    ld = DataLoader(batch_load_fn=loader)
    items = await asyncio.gather(ld.load(1), ld.load(2)) 
    
    assert items == [Data(a=1), Data(a=2)]


@pytest.mark.asyncio
async def test_transoform_decorator_4():
    class Data(BaseModel):
        a: int

    async def loader(keys):
        return keys

    def fn(x):
        return Data(a=x)
    
    _loader = util.transformer_decorator(fn)(loader)
    ld = DataLoader(batch_load_fn=_loader)
    items = await asyncio.gather(ld.load(1), ld.load(2)) 
    
    assert items == [Data(a=1), Data(a=2)]


@pytest.mark.asyncio
async def test_replace_method():
    class A():
        def __init__(self, name: str):
            self.name = name

        async def say(self, arr: List[str]):
            return f'{self.name}, {len(arr)}'

    a = A('kikodo')
    r1 = await a.say(['1'])
    assert r1 == 'kikodo, 1'

    async def kls_method(self, *args):
        v = await A.say(self, *args)
        return f'hello, {v}'

    AA = util.replace_method(A, 'AA', 'say', kls_method)
    k = AA('kimi')
    r2 = await k.say(['1', '2', '3'])

    assert r2 == 'hello, kimi, 3'
    assert AA.__name__ == 'AA'


def test_super_logic():
    class A():
        def say(self):
            return 'A'
    
    class B(A):
        def say(self):
            val = A().say()
            return f'B.{val}'
    

    b = B()
    assert b.say() == 'B.A'