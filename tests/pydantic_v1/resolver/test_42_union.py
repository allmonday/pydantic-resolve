from typing import Union
from pydantic import BaseModel, Field
from pydantic_resolve import Resolver
import pytest


class A(BaseModel):
    id: str


class B(BaseModel):
    id: str
    name: str


class Container(BaseModel):
    items: list[Union[B, A]] = Field(default_factory=list)

    def resolve_items(self):
        return [dict(id='1'), dict(id='2', name='Item 2')]


@pytest.mark.asyncio
async def test_type_definition():
    c = Container()
    result = await Resolver().resolve(c)
    expected = {
        'items': [
            {'id': '1'},
            {'id': '2', 'name': 'Item 2'}
        ]
    }
    assert result.dict() == expected

class Container1(BaseModel):
    items: list[Union[B, A]] = Field(default_factory=list)

    def resolve_items(self):
        return [A(id='1'), B(id='2', name='Item 2')]


@pytest.mark.asyncio
async def test_type_definition_1():
    c = Container1()
    result = await Resolver().resolve(c)
    expected = {
        'items': [
            {'id': '1'},
            {'id': '2', 'name': 'Item 2'}
        ]
    }
    assert result.dict() == expected

class Container2(BaseModel):
    items: list[Union[A, B]] = [A(id='1'), B(id='2', name='Item 2')]

@pytest.mark.asyncio
async def test_type_definition_2():
    c = Container2()
    expected = {
        'items': [
            {'id': '1'},
            {'id': '2', 'name': 'Item 2'}
        ]
    }
    assert c.dict() == expected