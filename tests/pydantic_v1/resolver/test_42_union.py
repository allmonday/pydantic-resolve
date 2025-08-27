from typing import Union, List
from pydantic import BaseModel, Field
from pydantic_resolve import Resolver
import pytest


class A(BaseModel):
    id: str
    age: int


class B(BaseModel):
    id: str
    name: str


class Container1(BaseModel):
    items: List[Union[A, B]] = Field(default_factory=list)

    def resolve_items(self):
        return [A(id='1', age=11), B(id='2', name='Item 2')]


@pytest.mark.asyncio
async def test_type_definition_1():
    c = Container1()
    result = await Resolver().resolve(c)
    expected = {
        'items': [
            {'id': '1', 'age': 11},
            {'id': '2', 'name': 'Item 2'}
        ]
    }
    assert result.dict() == expected
