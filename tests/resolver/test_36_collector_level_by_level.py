from __future__ import annotations
from pydantic import BaseModel
from typing import List, Tuple
from pydantic_resolve import Resolver, Collector
import pytest


class Root(BaseModel):
    list_a: List[A] = []
    def resolve_list_a(self):
        return data
    
    names: List[Tuple[str, int]] = []
    def post_names(self, collector=Collector('b_name')):
        return collector.values()

class A(BaseModel):
    list_b: List[B]

    names: List[Tuple[str, int]] = []
    def post_names(self, collector=Collector('b_name')):
        return collector.values()

class B(BaseModel):
    __pydantic_resolve_collect__ = {
        ('name', 'age'): 'b_name'
    }

    name: str
    age: int


data = [
        {'list_b': [
            {'name': 'b1', "age": 1},
            {'name': 'b2', "age": 2},
        ]},
        {'list_b': [
            {'name': 'b3', "age": 3},
            {'name': 'b4', "age": 4},
        ]},
    ]
    

@pytest.mark.asyncio
async def test_level():
    r = Root()
    resolver = Resolver()
    r = await resolver.resolve(r)
    # print(resolver.object_collect_alias_map_store)
    assert r.dict() == {
        "list_a": [
            {
            "list_b": [
                {
                "name": "b1",
                "age": 1
                },
                {
                "name": "b2",
                "age": 2
                }
            ],
            "names": [
                ("b1", 1),
                ("b2", 2)
            ]
            },
            {
            "list_b": [
                {
                "name": "b3",
                "age": 3
                },
                {
                "name": "b4",
                "age": 4
                }
            ],
            "names": [
                ("b3", 3),
                ("b4", 4)
            ]
            }
        ],
        "names": [
            ("b1", 1),
            ("b2", 2),
            ("b3", 3),
            ("b4", 4),
        ]
    }