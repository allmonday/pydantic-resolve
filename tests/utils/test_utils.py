import asyncio
from dataclasses import dataclass
from typing import List
from pydantic_resolve import util
from pydantic import BaseModel
import pytest

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
    assert list(output) == [b, c, a, None]
    

def test_build_list():
    raw = [(1, 'peter', 10), (2, 'mike', 21), (3, 'john', 12)]
    users = [User(id=i[0], name=i[1], age=i[2]) for i in raw]
    a, b, c = users
    ids = [2, 3, 1, 4]
    output = util.build_list(users, ids, lambda x: x.id)
    assert list(output) == [[b], [c], [a], []]

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



@pytest.mark.asyncio
async def test_mapper_1():
    class A(BaseModel):
        a: int

    @util.mapper(lambda x: A(**x))
    async def foo():
        return {'a': 1}

    async def call_later(f):
        await asyncio.sleep(1)
        f.set_result({'a': 1})

    @util.mapper(lambda x: A(**x))
    async def bar():
        lp = asyncio.get_event_loop()
        f = lp.create_future()
        asyncio.create_task(call_later(f))
        return f
    
    ret = await foo()
    ret2 = await bar()
    assert ret == A(a=1)
    assert ret2 == A(a=1)


def test_auto_mapper_1():
    class A(BaseModel):
        a: int
    
    params = (A, {'a': 1})
    ret = util.get_mapping_rule(*params)(*params)  # type:ignore
    assert ret == A(a=1)
    
    @dataclass
    class B:
        a: int

    params2 = (B, {'a': 1})
    ret2 = util.get_mapping_rule(*params2)(*params2) # type:ignore
    assert ret2 == B(a=1)


def test_auto_mapper_2():
    class A(BaseModel):
        a: int
        class Config:
            orm_mode=True
    
    class AA:
        def __init__(self, a):
            self.a = a
    
    p1 = (A, AA(1))
    ret = util.get_mapping_rule(*p1)(*p1)  # type: ignore
    assert ret == A(a=1)

    p2 = (A, {'a': 1})
    with pytest.raises(AttributeError):
        util.get_mapping_rule(*p2)  # type: ignore
    

def test_auto_mapper_3():
    class A(BaseModel):
        a: int
        class Config:
            orm_mode=True
    
    p1 = (A, A(a=1))
    rule = util.get_mapping_rule(*p1)  # type: ignore

    assert rule is None
    output = util.apply_rule(rule, *p1, is_list=False)
    assert output == A(a=1)


def test_auto_mapper_4():
    class A(BaseModel):
        a: int

    class AA:
        def __init__(self, a):
            self.a = a
    
    p1 = (A, AA(a=1))
    with pytest.raises(AttributeError):
        util.get_mapping_rule(*p1)(*p1)  # type: ignore

