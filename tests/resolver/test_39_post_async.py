import asyncio
from pydantic import BaseModel
from pydantic_resolve import Resolver
import pytest


class A(BaseModel):
    name: str

    greet: str = ''
    async def post_greet(self):
        await asyncio.sleep(1)
        return 'hello ' + self.name

@pytest.mark.asyncio
async def test_post_async():
    data = await Resolver().resolve(A(name='kikodo'))
    assert data.greet == 'hello kikodo'
