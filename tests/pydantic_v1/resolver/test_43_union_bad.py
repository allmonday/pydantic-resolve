from typing import Union
from pydantic import BaseModel, Field
from pydantic_resolve import Resolver
import pytest


class A(BaseModel):
    id: str


class B(BaseModel):
    id: str
    name: str


class Container1(BaseModel):
    items: list[Union[A, B]] = Field(default_factory=list)

    def resolve_items(self):
        return [A(id='1'), B(id='2', name='Item 2')]
    
    class Config:
        smart_union = True # not work https://docs.pydantic.dev/1.10/usage/model_config/#smart-union


@pytest.mark.asyncio
async def test_type_definition_1():
    c = Container1()
    result = await Resolver().resolve(c)
    expected = {
        'items': [
            {'id': '1'},
            {'id': '2'} # B would be converted as A if it is convertable.
        ]
    }
    assert result.dict() == expected
