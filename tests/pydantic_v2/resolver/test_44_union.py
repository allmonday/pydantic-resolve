from typing import Union
from pydantic import BaseModel
from pydantic_resolve import Resolver
import pytest


class A(BaseModel):
    id: str


class B(BaseModel):
    id: str
    name: str


class C(BaseModel):
    id: str
    name: str


Item = Union[A, B, C]


class Container(BaseModel):
    items: list[Item] = []

    def resolve_items(self):
        return [A(id='1'), B(id='2', name='Item 2')]


@pytest.mark.asyncio
async def test_type_definition():
    c = Container()
    resolver = Resolver()
    result = await resolver.resolve(c)
    expected = {
        'items': [
            {'id': '1'},
            {'id': '2', 'name': 'Item 2'}
        ],
    }
    assert result.model_dump() == expected
