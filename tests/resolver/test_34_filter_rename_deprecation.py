from pydantic import BaseModel
from typing import List
from pydantic_resolve import Resolver, LoaderDepend
from aiodataloader import DataLoader
import pytest
from pydantic_resolve.exceptions import GlobalLoaderFieldOverlappedError

class LoaderA(DataLoader):
    power: int
    async def batch_load_fn(self, keys: List[int]):
        return [ k** self.power for k in keys ]

class LoaderB(DataLoader):
    power: int
    async def batch_load_fn(self, keys: List[int]):
        return [ k** self.power for k in keys ]

class LoaderC(DataLoader):
    power: int
    add: int 
    async def batch_load_fn(self, keys: List[int]):
        return [ k** self.power + self.add for k in keys ]


async def loader_fn_a(keys):
    return [ k**2 for k in keys ]

class A(BaseModel):
    val: int

    a: int = 0
    def resolve_a(self, loader=LoaderDepend(LoaderA)):
        return loader.load(self.val)

    b: int = 0
    def resolve_b(self, loader=LoaderDepend(LoaderB)):
        return loader.load(self.val)

    c: int = 0
    def resolve_c(self, loader=LoaderDepend(LoaderC)):
        return loader.load(self.val)


@pytest.mark.asyncio
async def test_case_0():
    data = [A(val=n) for n in range(3)]
    with pytest.warns(DeprecationWarning):
        data = await Resolver(global_loader_filter={'power': 2}, 
                            loader_filters={LoaderC:{'add': 1}}).resolve(data)


@pytest.mark.asyncio
async def test_case_1():
    data = [A(val=n) for n in range(3)]
    with pytest.warns(DeprecationWarning):
        data = await Resolver(loader_filters={LoaderA:{'power': 2}, 
                                            LoaderB:{'power': 3},
                                            LoaderC:{'power': 3, 'add': 1}}).resolve(data)

