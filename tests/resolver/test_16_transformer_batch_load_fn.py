from __future__ import annotations
import pytest
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend

@pytest.mark.asyncio
async def test_loader_depends_1():
    async def batch_load_fn(keys):
        return keys

    class Student(BaseModel):
        id: int
        name: str

        str_id: str = ''
        def resolve_str_id(self, loader=LoaderDepend(batch_load_fn, lambda x: str(x))):
            return loader.load(self.id)

    students = [Student(id=1, name="jack")]
    results = await Resolver().resolve(students)

    source = [r.dict() for r in results]
    expected = [
        {'id': 1, 'name': 'jack', 'str_id': '1' }]

    assert source == expected


@pytest.mark.asyncio
async def test_loader_depends_2():
    async def batch_load_fn(keys):
        return keys

    class Student(BaseModel):
        id: int
        name: str

        str_id: str = ''
        def resolve_str_id(self, loader=LoaderDepend(batch_load_fn, lambda x: str(x))):
            return loader.load(self.id)

        x_id: str = ''
        def resolve_x_id(self, loader=LoaderDepend(batch_load_fn, lambda x: f'prefix-{x}')):
            return loader.load(self.id)

    students = [Student(id=1, name="jack")]
    results = await Resolver().resolve(students)

    source = [r.dict() for r in results]
    expected = [{ 'id': 1, 'name': 'jack', 'str_id': '1', 'x_id': 'prefix-1' }]

    assert source == expected
