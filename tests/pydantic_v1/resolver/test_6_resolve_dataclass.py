from dataclasses import dataclass, asdict, field
import asyncio
from pydantic_resolve import Resolver
from typing import List
import pytest

@dataclass
class Wheel:
    is_ok: bool 

@dataclass
class Car:
    name: str
    wheels: List[Wheel] = field(default_factory=list)

    async def resolve_wheels(self) -> List[Wheel]:
        await asyncio.sleep(.1)
        return [Wheel(is_ok=True)]

@pytest.mark.asyncio
async def test_resolve_dataclass_1():
    car = Car(name="byd")
    result = await Resolver().resolve(car)
    expected = {
        'name': 'byd',
        'wheels': [{'is_ok': True}]
    }
    assert asdict(result) == expected

@pytest.mark.asyncio
async def test_resolver_dataclass_2():
    car = [Car(name="byd")]
    result = await Resolver().resolve(car)
    expected = {
        'name': 'byd',
        'wheels': [{'is_ok': True}]
    }
    assert asdict(result[0]) == expected