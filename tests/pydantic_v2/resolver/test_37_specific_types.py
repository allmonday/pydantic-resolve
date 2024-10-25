import pytest
from typing import Tuple
from pydantic import BaseModel
from pydantic_resolve import Resolver

class Case(BaseModel):
    value: Tuple[int, int]=(0,0)

    def resolve_value(self):
        return (1, 1)


@pytest.mark.asyncio
async def test_works():
    # https://github.com/allmonday/pydantic2-resolve/issues/7
    result = await Resolver().resolve(Case())
    assert result.value == (1, 1)