import pytest
from typing import List, Optional
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
    
    kar_c: Optional[str] = None
    def resolve_kar_c(self, ancestor_context):
        return ancestor_context['foo_c']


class Bar(BaseModel):
    __pydantic_resolve_expose__ = {'num': 'bar_num'}

    num: int

    kars: List[Kar] = []
    def resolve_kars(self):
        return [{'name': n} for n in ['a', 'b', 'c']]


class Foo(BaseModel):
    __pydantic_resolve_expose__ = {'a': 'foo_a', 'b': 'foo_b', 'c': 'foo_c'}

    a: str
    b: str
    c: Optional[str] = None
    nums:List[int]
    bars: List[Bar] = []

    def resolve_bars(self):
        return [{'num': n} for n in self.nums]


@pytest.mark.asyncio
async def test_case():
    foo = Foo(nums=[1,2,3], a='a', b='b', c=None)
    await Resolver().resolve(foo)
    assert foo.model_dump() == {
        'a': 'a',
        'b': 'b',
        'c': None,
        'nums': [1,2,3],
        'bars': [
            {'num': 1, 'kars': [ 
                {'name': 'a', 'desc': 'a - 1 - a - b', 'output': 'a - 1 - a - b', 'kar_c': None},
                {'name': 'b', 'desc': 'b - 1 - a - b', 'output': 'b - 1 - a - b', 'kar_c': None},
                {'name': 'c', 'desc': 'c - 1 - a - b', 'output': 'c - 1 - a - b', 'kar_c': None} ]},
            {'num': 2, 'kars': [ 
                {'name': 'a', 'desc': 'a - 2 - a - b', 'output': 'a - 2 - a - b', 'kar_c': None},
                {'name': 'b', 'desc': 'b - 2 - a - b', 'output': 'b - 2 - a - b', 'kar_c': None},
                {'name': 'c', 'desc': 'c - 2 - a - b', 'output': 'c - 2 - a - b', 'kar_c': None} ]},
            {'num': 3, 'kars': [ 
                {'name': 'a', 'desc': 'a - 3 - a - b', 'output': 'a - 3 - a - b', 'kar_c': None},
                {'name': 'b', 'desc': 'b - 3 - a - b', 'output': 'b - 3 - a - b', 'kar_c': None},
                {'name': 'c', 'desc': 'c - 3 - a - b', 'output': 'c - 3 - a - b', 'kar_c': None} ]}
        ]
    }