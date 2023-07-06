import pytest
from pydantic import BaseModel
from typing import Optional
from pydantic_resolve import resolve
import asyncio

class C(BaseModel):
    name: str = ''

class B(BaseModel):
    name: str
    c: Optional[C] = None
    async def resolve_c(self) -> Optional[C]:
        await asyncio.sleep(1)
        return C(name='hello world')

class A(BaseModel):
    b: B

@pytest.mark.asyncio
async def test_resolve_object():
    s = A(b=B(name="kikodo"))
    result = await resolve(s)
    expected = {
        "b": {
            "name":"kikodo",
            "c": {
                "name": "hello world"
            }
        }
    }
    assert result.dict() == expected
