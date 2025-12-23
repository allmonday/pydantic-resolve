import pytest
from typing import List
from pydantic import BaseModel
from pydantic_resolve.resolver import Resolver


@pytest.mark.asyncio
async def test_case_0():
    class Kar(BaseModel):
        name: str

        desc: str = ''
        def resolve_desc(self, ancestor_context):
            return f"{self.name} - {ancestor_context['bar_num']}"


    class Bar(BaseModel):
        __pydantic_resolve_expose__ = {'num': 'bar_num'}

        num: int

        kars: List[Kar] = []
        def resolve_kars(self):
            return [{'name': n} for n in ['a', 'b', 'c']]


    class Foo(BaseModel):
        __pydantic_resolve_expose__ = {'nums': 'bar_num'}

        nums:List[int]
        bars: List[Bar] = []

        def resolve_bars(self):
            return [{'num': n} for n in self.nums]


    foo = Foo(nums=[1,2,3])
    with pytest.raises(ValueError) as e:
        await Resolver().resolve(foo)
    assert 'alias name conflicts, please check' in str(e.value)


@pytest.mark.asyncio
async def test_case_1():
    class Kar(BaseModel):
        name: str

        desc: str = ''
        def resolve_desc(self, ancestor_context):
            return f"{self.name} - {ancestor_context['bar_num']}"


    class Bar(BaseModel):
        __pydantic_resolve_expose__ = ['num', 'bar_num']

        num: int

        kars: List[Kar] = []
        def resolve_kars(self):
            return [{'name': n} for n in ['a', 'b', 'c']]


    class Foo(BaseModel):
        nums:List[int]
        bars: List[Bar] = []

        def resolve_bars(self):
            return [{'num': n} for n in self.nums]


    foo = Foo(nums=[1,2,3])
    with pytest.raises(TypeError) as e:
        await Resolver().resolve(foo)
    assert 'is not dict' in str(e.value)


@pytest.mark.asyncio
async def test_case_2():
    class Kar(BaseModel):
        name: str

        desc: str = ''
        def resolve_desc(self, ancestor_context):
            return f"{self.name} - {ancestor_context['bar_num']}"


    class Bar(BaseModel):
        __pydantic_resolve_expose__ = {'xnum': 'bar_num'}

        num: int

        kars: List[Kar] = []
        def resolve_kars(self):
            return [{'name': n} for n in ['a', 'b', 'c']]


    class Foo(BaseModel):
        nums:List[int]
        bars: List[Bar] = []

        def resolve_bars(self):
            return [{'num': n} for n in self.nums]


    foo = Foo(nums=[1,2,3])
    with pytest.raises(AttributeError) as e:
        await Resolver().resolve(foo)
    assert 'does not existed' in str(e.value)