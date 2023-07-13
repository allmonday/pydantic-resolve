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
        await asyncio.sleep(1)  # mock i/o
        return random() > 0.5
    
class Earth(BaseModel):
    humans: List[Human] = []
    def resolve_humans(self, context):
        return [dict(name=f'man-{i}') for i in range(context['count'])]

class EarthBad(BaseModel):
    humans: List[Human] = []
    def resolve_humans(self, context):
        context['name'] = 'earth'  # mappingproxytype will raise TypeError
        return [dict(name=f'man-{i}') for i in range(context['count'])]

@pytest.mark.asyncio
async def test_1():
    earth = Earth()
    earth = await Resolver(context={'count': 10}).resolve(earth)
    assert len(earth.humans) == 10


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