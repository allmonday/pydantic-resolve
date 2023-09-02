import pytest
from typing import List
from pydantic import BaseModel
from pydantic_resolve.resolver import Resolver


class Kar(BaseModel):
    name: str

    desc: str = ''
    def resolve_desc(self, ancestor_context):
        return f"{self.name} - {ancestor_context['bar_num']} - {ancestor_context['foo_a']} - {ancestor_context['foo_b']}"
    
    output: str = ''
    def post_output(self, ancestor_context):
        return f"{self.name} - {ancestor_context['bar_num']} - {ancestor_context['foo_a']} - {ancestor_context['foo_b']}"


class Bar(BaseModel):
    __pydantic_resolve_expose__ = {'num': 'bar_num'}

    num: int

    kars: List[Kar] = []
    def resolve_kars(self):
        return [{'name': n} for n in ['a', 'b', 'c']]


class Foo(BaseModel):
    __pydantic_resolve_expose__ = {'a': 'foo_a', 'b': 'foo_b'}

    a: str
    b: str
    nums:List[int]
    bars: List[Bar] = []

    def resolve_bars(self):
        return [{'num': n} for n in self.nums]


@pytest.mark.asyncio
async def test_case():
    foo = Foo(nums=[1,2,3], a='a', b='b')
    await Resolver().resolve(foo)
    assert foo.dict() == {
        'a': 'a',
        'b': 'b',
        'nums': [1,2,3],
        'bars': [
            {'num': 1, 'kars': [ 
                {'name': 'a', 'desc': 'a - 1 - a - b', 'output': 'a - 1 - a - b'},
                {'name': 'b', 'desc': 'b - 1 - a - b', 'output': 'b - 1 - a - b'},
                {'name': 'c', 'desc': 'c - 1 - a - b', 'output': 'c - 1 - a - b'} ]},
            {'num': 2, 'kars': [ 
                {'name': 'a', 'desc': 'a - 2 - a - b', 'output': 'a - 2 - a - b'},
                {'name': 'b', 'desc': 'b - 2 - a - b', 'output': 'b - 2 - a - b'},
                {'name': 'c', 'desc': 'c - 2 - a - b', 'output': 'c - 2 - a - b'} ]},
            {'num': 3, 'kars': [ 
                {'name': 'a', 'desc': 'a - 3 - a - b', 'output': 'a - 3 - a - b'},
                {'name': 'b', 'desc': 'b - 3 - a - b', 'output': 'b - 3 - a - b'},
                {'name': 'c', 'desc': 'c - 3 - a - b', 'output': 'c - 3 - a - b'} ]}
        ]
    }