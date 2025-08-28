from typing import Union, List
from pydantic import BaseModel
from pydantic_resolve import Resolver, Loader
import pytest


async def batch_load_fn(keys):
    return [1 for k in keys]

class A(BaseModel):
    id: str
    def post_id(self):
        return self.id + "-"

    n: int = 0
    def resolve_n(self, loader=Loader(batch_load_fn)):
        return loader.load(self.id)

class B(BaseModel):
    id: str
    name: str
    def post_id(self):
        return self.id + "+"

    n: int = 0
    def resolve_n(self, loader=Loader(batch_load_fn)):
        return loader.load(self.id)

class C(BaseModel):
    id: str
    name: str


Item = Union[A, B, C]


class Container(BaseModel):
    items: List[Item] = []

    def resolve_items(self):
        return [A(id='1'), B(id='2', name='Item 2')]


@pytest.mark.asyncio
async def test_type_definition():
    c = Container()
    resolver = Resolver()
    result = await resolver.resolve(c)
    expected = {
        'items': [
            {'id': '1-', 'n': 1},
            {'id': '2+', 'name': 'Item 2', 'n': 1}
        ],
    }
    assert result.model_dump() == expected
