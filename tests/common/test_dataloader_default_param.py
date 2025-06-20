from pydantic import BaseModel
from typing import List
from pydantic_resolve import Resolver, LoaderDepend
from aiodataloader import DataLoader
import pytest

class LoaderA(DataLoader):
    power: int = 2
    async def batch_load_fn(self, keys: List[int]):
        return [ k** self.power for k in keys ]

class A(BaseModel):
    val: int

    a: int = 0
    def resolve_a(self, loader=LoaderDepend(LoaderA)):
        return loader.load(self.val)

@pytest.mark.asyncio
async def test_case():
    """
    default param allow not setting loader param in Resolver
    """
    data = [A(val=n) for n in range(3)] # 0, 1, 2 => 0, 1, 4
    data = await Resolver().resolve(data)
    assert data[2].a == 4

@pytest.mark.asyncio
async def test_case_2():
    """
    default param can be overridden in Resolver
    """
    data = [A(val=n) for n in range(3)] # 0, 1, 2 => 0, 1, 4
    data = await Resolver(
        loader_params={
            LoaderA: {'power': 3}  # override default power
        }
    ).resolve(data)
    assert data[2].a == 8
