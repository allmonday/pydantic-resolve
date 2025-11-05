from pydantic import BaseModel
from pydantic_resolve import Resolver
from pydantic_resolve.constant import METADATA_CACHE
import pytest


class Container(BaseModel):
    name: str = ''
    def resolve_name(self):
        return 'hello'


@pytest.mark.asyncio
async def test_cache_of_metadata():
    c = Container()
    result = await Resolver().resolve(c)
    expected = {
        'name': 'hello',
    }
    assert result.model_dump() == expected
    assert getattr(Container, METADATA_CACHE) is not None

    c2 = Container()
    result2 = await Resolver().resolve(c2)
    assert result2.model_dump() == expected
