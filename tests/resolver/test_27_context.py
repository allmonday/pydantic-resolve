import asyncio
from random import random
from pydantic import BaseModel
from pydantic_resolve import Resolver
from typing import List
import pytest

class Human(BaseModel):
    name: str
    lucky: bool = True
    async def resolve_lucky(self):
        print('calculating...')
        await asyncio.sleep(0.1)  # mock i/o
        return random() > 0.5
    
class Earth(BaseModel):
    humans: List[Human] = []
    def resolve_humans(self, context):
        return [dict(name=f'man-{i}') for i in range(context['count'])]
    
    count: int = 0
    def post_count(self, context):
        return context['count']

class EarthBad(BaseModel):
    humans: List[Human] = []
    def resolve_humans(self, context):
        context['name'] = 'earth'  # mappingproxytype will raise TypeError
        return [dict(name=f'man-{i}') for i in range(context['count'])]

class EarthBad2(BaseModel):
    humans: List[Human] = []
    def resolve_humans(self, context):
        return [dict(name=f'man-{i}') for i in range(context['count'])]
    
    count: int = 0
    def post_count(self, context):
        context['count'] = 111
        return context['count']


@pytest.mark.asyncio
async def test_1():
    earth = Earth()
    earth = await Resolver(context={'count': 10}).resolve(earth)
    assert len(earth.humans) == 10
    assert earth.count == 10


@pytest.mark.asyncio
async def test_2():
    earth = Earth()
    with pytest.raises(AttributeError):
        await Resolver().resolve(earth)

@pytest.mark.asyncio
async def test_3():
    earth = Earth()
    with pytest.raises(KeyError):
        await Resolver(context={'age': 10}).resolve(earth)

@pytest.mark.asyncio
async def test_4():
    earth = EarthBad()
    with pytest.raises(TypeError):
        await Resolver(context={'count': 10}).resolve(earth)

@pytest.mark.asyncio
async def test_5():
    earth = EarthBad2()
    with pytest.raises(TypeError):
        await Resolver(context={'count': 10}).resolve(earth)


def test_6_empty_context_dict_rejected():
    """Resolver(context={}) is rejected up-front rather than silently coerced to None.

    See #291: previously the empty dict was falsy so self.context became None,
    and the user only found out later via the unrelated `AttributeError:
    context is missing` from the has_context check.
    """
    with pytest.raises(ValueError, match='context must be a non-empty dict'):
        Resolver(context={})


@pytest.mark.parametrize('bad', [[1, 2, 3], ('a', 'b'), 'string', 42, object()])
def test_7_non_dict_context_rejected(bad):
    """Non-dict context values are rejected with TypeError at __init__,
    rather than slipping through to MappingProxyType's opaque TypeError."""
    with pytest.raises(TypeError, match='context must be a dict'):
        Resolver(context=bad)


def test_8_none_context_still_allowed():
    """Resolver() and Resolver(context=None) must remain valid — the rejection
    only targets the nonsensical empty-dict / wrong-type cases."""
    assert Resolver().context is None
    assert Resolver(context=None).context is None
