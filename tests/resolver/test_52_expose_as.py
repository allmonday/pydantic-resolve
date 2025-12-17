from __future__ import annotations
import pytest
from typing import Optional, Annotated
from pydantic import BaseModel
from pydantic_resolve import Resolver, ExposeAs

class A(BaseModel):

    name: Annotated[str, ExposeAs('A_name')] = ''
    b: Optional[B] = None
    def resolve_b(self):
        return dict(name='b')

class B(BaseModel):
    name: str
    c: Optional[C] = None
    def resolve_c(self):
        return dict(name='c')

class C(BaseModel):
    name: str

    a_name: str = ''
    def post_a_name(self, ancestor_context):
        return ancestor_context['A_name']


@pytest.mark.asyncio
async def test_expose_as():
    a = A(name='a_name')
    a = await Resolver().resolve(a)
    assert a.b.c.a_name == 'a_name'


class AA(BaseModel):
    __pydantic_resolve_expose__ = {
        'name': 'A_name'
    }
    name: Annotated[str, ExposeAs('A_name')] = ''
    b: Optional[B] = None
    def resolve_b(self):
        return dict(name='b')


@pytest.mark.asyncio
async def test_expose_as_attr_error():
    a = AA(name='a_name')
    with pytest.raises(AttributeError):
        await Resolver().resolve(a)