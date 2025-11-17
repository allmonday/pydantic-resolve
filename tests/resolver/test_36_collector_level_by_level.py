from __future__ import annotations
from pydantic import BaseModel
from typing import List
from pydantic_resolve import Resolver, Collector
import pytest


class Root(BaseModel):
    list_a: List[A] = []
    def resolve_list_a(self):
        return data
    
    names: List[str] = []
    def post_names(self, collector=Collector('b_name')):
        return collector.values()

class A(BaseModel):
    list_b: List[B]

    names: List[str] = []
    def post_names(self, collector=Collector('b_name')):
        return collector.values()

class B(BaseModel):
    __pydantic_resolve_collect__ = {'name': 'b_name'}
    name: str


data = [
        {'list_b': [
            {'name': 'b1'},
            {'name': 'b2'},
        ]},
        {'list_b': [
            {'name': 'b3'},
            {'name': 'b4'},
        ]},
    ]

@pytest.mark.asyncio
async def test_level():
    r = Root()
    resolver = Resolver()
    r = await resolver.resolve(r)
    # print(resolver.object_collect_alias_map_store)
    assert r.model_dump() == {
        "list_a": [
            {
            "list_b": [
                {
                "name": "b1"
                },
                {
                "name": "b2"
                }
            ],
            "names": [
                "b1",
                "b2"
            ]
            },
            {
            "list_b": [
                {
                "name": "b3"
                },
                {
                "name": "b4"
                }
            ],
            "names": [
                "b3",
                "b4"
            ]
            }
        ],
        "names": [
            "b1",
            "b2",
            "b3",
            "b4"
        ]
    }