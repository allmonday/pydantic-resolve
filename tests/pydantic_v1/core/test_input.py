from pydantic_resolve import Resolver
import pytest

@pytest.mark.asyncio
async def test_input():
    data = []
    data = await Resolver().resolve(data)
    assert data == []


@pytest.mark.asyncio
async def test_input_2():
    data = 'hello' 
    with pytest.raises(AttributeError):
        await Resolver().resolve(data)
