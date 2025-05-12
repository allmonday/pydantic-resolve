from typing import Optional
from pydantic import BaseModel
from pydantic_resolve.analysis import scan_and_store_metadata

class E(BaseModel):
    id: int
    def resolve_id(self):
        return self.id

class D(BaseModel):
    id: int
    e: E

class C(BaseModel):
    """
    INTRODUCTION:

    before ver: 1.11.8
    d, or e will be removed from the object_fields
    it is due to the _has_config function do not verify the len of 
    object_fields.

    but in fact, if a kls is cached, it should not take party in judging
    `should_treverse`, so from 1.11.9 it will return None
    """

    id: int
    d: D
    e: D

class BaseB(BaseModel):
    c: C

class B(BaseB):
    id: int

class A(BaseModel):
    id: int
    c: E  # travers once, then populate the cache info
    b: B


def test_long_distance_resolve():
    result = scan_and_store_metadata(A)
    prefix = 'tests.common.test_long_distance_resolve'
    expect = {
        f'{prefix}.A': {
            'resolve': [],
            'post': [],
            'object_fields': [ 'c', 'b'],
            'expose_dict': {},
            'collect_dict': {},
        },
        f'{prefix}.B': {
            'resolve': [],
            'post': [],
            'object_fields': ['c'],
            'expose_dict': {},
            'collect_dict': {},
        },
        f'{prefix}.C': {
            'resolve': [],
            'post': [],
            'object_fields': ['d', 'e'],
            'expose_dict': {},
            'collect_dict': {},
        },

        # before and include 1.11.8, it looks like
        # f'{prefix}.C': {
        #     'resolve': [],
        #     'post': [],
        #     'object_fields': ['d'],  # or ['e']
        #     'expose_dict': {},
        #     'collect_dict': {},
        # },

        f'{prefix}.D': {
            'resolve': [],
            'post': [],
            'object_fields': ['e'],
            'expose_dict': {},
            'collect_dict': {},
        },
        f'{prefix}.E': {
            'resolve': ['resolve_id'],
            'post': [],
            'object_fields': [],
            'expose_dict': {},
            'collect_dict': {},
        }
    }
    from pprint import pprint
    pprint(result)
    for k, v in result.items():
        assert expect[k].items() <= v.items()