import asyncio
from pydantic import ConfigDict, BaseModel
import pytest

import pydantic_resolve.utils.class_util
import pydantic_resolve.utils.conversion
import pydantic_resolve.utils.dataloader

def test_get_class_field_annotations():
    class B:
        hello: str = 'hello'

    class C:
        hello: str

        def __init__(self, c: str):
            self.c = c
        
    class D(C):
        pass

    class E(C):
        world: str
    
    assert list(pydantic_resolve.utils.class_util.get_fields_default_value_not_provided(B)) == [('hello', True)]
    assert list(pydantic_resolve.utils.class_util.get_fields_default_value_not_provided(C)) == [('hello', False)]
    assert list(pydantic_resolve.utils.class_util.get_fields_default_value_not_provided(D)) == []
    assert list(pydantic_resolve.utils.class_util.get_fields_default_value_not_provided(E)) == [('world', False)]


class User(BaseModel):
    id: int
    name: str
    age: int


def test_build_object():
    raw = [(1, 'peter', 10), (2, 'mike', 21), (3, 'john', 12)]
    users = [User(id=i[0], name=i[1], age=i[2]) for i in raw]
    a, b, c = users
    ids = [2, 3, 1, 4]
    output = pydantic_resolve.utils.dataloader.build_object(users, ids, lambda x: x.id)
    assert list(output) == [b, c, a, None]
    

def test_build_list():
    raw = [(1, 'peter', 10), (2, 'mike', 21), (3, 'john', 12)]
    users = [User(id=i[0], name=i[1], age=i[2]) for i in raw]
    a, b, c = users
    ids = [2, 3, 1, 4]
    output = pydantic_resolve.utils.dataloader.build_list(users, ids, lambda x: x.id)
    assert list(output) == [[b], [c], [a], []]



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

    @pydantic_resolve.utils.conversion.mapper(lambda x: A(**x))
    async def foo():
        return {'a': 1}

    async def call_later(f):
        await asyncio.sleep(.1)
        f.set_result({'a': 1})

    @pydantic_resolve.utils.conversion.mapper(lambda x: A(**x))
    async def bar():
        lp = asyncio.get_event_loop()
        f = lp.create_future()
        asyncio.create_task(call_later(f))
        return f
    
    ret = await foo()
    ret2 = await bar()
    assert ret == A(a=1)
    assert ret2 == A(a=1)


def test_auto_mapper_2():
    class A(BaseModel):
        a: int
        model_config = ConfigDict(from_attributes=True)
    
    class AA:
        def __init__(self, a):
            self.a = a
    
    p1 = (A, AA(1))
    ret = pydantic_resolve.utils.conversion._get_mapping_rule(*p1)(*p1)  # type: ignore
    assert ret == A(a=1)

    p2 = (A, {'a': 1})
    with pytest.raises(AttributeError):
        pydantic_resolve.utils.conversion._get_mapping_rule(*p2)  # type: ignore
    

def test_auto_mapper_3():
    class A(BaseModel):
        a: int
        model_config = ConfigDict(from_attributes=True)
    
    p1 = (A, A(a=1))
    rule = pydantic_resolve.utils.conversion._get_mapping_rule(*p1)  # type: ignore

    assert rule is None
    output = pydantic_resolve.utils.conversion._apply_rule(rule, *p1, is_list=False)
    assert output == A(a=1)


def test_auto_mapper_4():
    class A(BaseModel):
        a: int

    class AA:
        def __init__(self, a):
            self.a = a
    
    p1 = (A, AA(a=1))
    with pytest.raises(AttributeError):
        pydantic_resolve.utils.conversion._get_mapping_rule(*p1)(*p1)  # type: ignore

