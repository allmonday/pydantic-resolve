import pytest
from pydantic import BaseModel
from typing import Optional
from pydantic_resolve import Resolver
import asyncio

class D(BaseModel):
    name: str = 'kikodo'
    age: int = 0
    def resolve_age(self):
        return 11

class C(BaseModel):
    name: str = ''
    d: D = D()


class B(BaseModel):
    name: str
    c: Optional[C] = None
    async def resolve_c(self) -> Optional[C]:
        await asyncio.sleep(.1)
        return C(name='hello world')

class A(BaseModel):
    b: B

class Z(BaseModel):
    a: A
    resolve_age: int

@pytest.mark.asyncio
async def test_resolve_object():
    s = Z(a=A(b=B(name="kikodo")), resolve_age=21)

    result = await Resolver().resolve(s)
    expected = {
        "a": {
            "b": {
                "name":"kikodo",
                "c": {
                    "name": "hello world",
                    "d": {
                        "name": "kikodo",
                        "age": 11
                    }
                }
            }
        },
        "resolve_age": 21
    }
    assert result.dict() == expected
