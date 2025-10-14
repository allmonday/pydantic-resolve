from __future__ import annotations
from typing import Union, Optional
from pydantic import BaseModel
from pydantic_resolve.analysis import Analytic

async def loader_fn(keys):
    return keys

class Leaf(BaseModel):
    id: int

class A(BaseModel):
    id: int
    leaf: Optional[Leaf] = None
    def resolve_leaf(self):
        return None

class B(BaseModel):
    id: int
    name: str

class X(BaseModel):
    items: Union[A, B]

    items2: Optional[Union[A, B]] = None
    def resolve_items2(self):
        return A(id=1)
    

def test_get_all_fields():
    result = Analytic().scan(X)
    expect = {
        'test_union.X': {
            'resolve': ['resolve_items2'],
            'post': [],
            'object_fields': ['items'],
            'expose_dict': {},
            'collect_dict': {}
        },
        'test_union.A': {
            'resolve': ['resolve_leaf'],
            'post': [],
            'object_fields': [],
            'expose_dict': {},
            'collect_dict': {}
        },
        'test_union.B': {
            'resolve': [],
            'post': [],
            'object_fields': [],
            'expose_dict': {},
            'collect_dict': {}
        },
        'test_union.Leaf': {
            'resolve': [],
            'post': [],
            'object_fields': [],
            'expose_dict': {},
            'collect_dict': {}
        },
    }
    for k, v in expect.items():
        assert  v.items() <= result[k].items()
