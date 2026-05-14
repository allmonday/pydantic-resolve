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


# ---- EmptyLoader tests ----

@pytest.mark.asyncio
async def test_strict_empty_loader_raises():
    from pydantic_resolve.utils.dataloader import StrictEmptyLoader
    loader = StrictEmptyLoader()
    with pytest.raises(ValueError, match='EmptyLoader should load from pre loaded data'):
        await loader.batch_load_fn([1, 2])


@pytest.mark.asyncio
async def test_list_empty_loader():
    from pydantic_resolve.utils.dataloader import ListEmptyLoader
    loader = ListEmptyLoader()
    result = await loader.batch_load_fn([1, 2, 3])
    assert result == [[], [], []]


@pytest.mark.asyncio
async def test_single_empty_loader():
    from pydantic_resolve.utils.dataloader import SingleEmptyLoader
    loader = SingleEmptyLoader()
    result = await loader.batch_load_fn([1, 2, 3])
    assert result == [None, None, None]


def test_generate_strict_empty_loader_creates_independent_class():
    from pydantic_resolve.utils.dataloader import generate_strict_empty_loader
    LoaderA = generate_strict_empty_loader('LoaderA')
    LoaderB = generate_strict_empty_loader('LoaderB')
    assert LoaderA.__name__ == 'LoaderA'
    assert LoaderB.__name__ == 'LoaderB'
    assert LoaderA is not LoaderB


def test_generate_list_empty_loader_creates_independent_class():
    from pydantic_resolve.utils.dataloader import generate_list_empty_loader
    LoaderA = generate_list_empty_loader('LoaderA')
    LoaderB = generate_list_empty_loader('LoaderB')
    assert LoaderA.__name__ == 'LoaderA'
    assert LoaderB.__name__ == 'LoaderB'
    assert LoaderA is not LoaderB


def test_generate_single_empty_loader_creates_independent_class():
    from pydantic_resolve.utils.dataloader import generate_single_empty_loader
    LoaderA = generate_single_empty_loader('LoaderA')
    LoaderB = generate_single_empty_loader('LoaderB')
    assert LoaderA.__name__ == 'LoaderA'
    assert LoaderB.__name__ == 'LoaderB'
    assert LoaderA is not LoaderB


@pytest.mark.asyncio
async def test_generated_loaders_have_independent_state():
    """Verify that generated loaders don't share mutable class state."""
    from pydantic_resolve.utils.dataloader import generate_list_empty_loader
    LoaderA = generate_list_empty_loader('LoaderA')
    LoaderB = generate_list_empty_loader('LoaderB')
    # Mutate one class attribute
    LoaderA.custom_attr = 'modified'
    assert not hasattr(LoaderB, 'custom_attr')


def test_copy_dataloader_kls_creates_independent_class():
    from aiodataloader import DataLoader
    from pydantic_resolve.utils.dataloader import copy_dataloader_kls

    class MyLoader(DataLoader):
        batch_size = 10
        async def batch_load_fn(self, keys):
            return keys

    CopiedA = copy_dataloader_kls('CopiedA', MyLoader)
    CopiedB = copy_dataloader_kls('CopiedB', MyLoader)

    assert CopiedA.__name__ == 'CopiedA'
    assert CopiedB.__name__ == 'CopiedB'
    assert CopiedA is not CopiedB
    assert CopiedA.batch_size == 10
    assert CopiedB.batch_size == 10


def test_copy_dataloader_kls_state_isolation():
    from aiodataloader import DataLoader
    from pydantic_resolve.utils.dataloader import copy_dataloader_kls

    class MyLoader(DataLoader):
        batch_size = 10
        async def batch_load_fn(self, keys):
            return keys

    CopiedA = copy_dataloader_kls('CopiedA', MyLoader)
    CopiedB = copy_dataloader_kls('CopiedB', MyLoader)

    CopiedA.batch_size = 99
    assert CopiedB.batch_size == 10

