from __future__ import annotations
from typing import List
import pytest
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend
from aiodataloader import DataLoader

@pytest.mark.asyncio
async def test_loader_depends():
    class BookLoader(DataLoader):
        async def batch_load_fn(self, keys):
            return ['a']

    class Student(BaseModel):
        id: int
        name: str

        books: List[str] = []
        def resolve_books(self, loader=LoaderDepend(BookLoader, lambda x: 'x')):
            return loader.load(self.id)

    students = [Student(id=1, name="jack")]
    results = await Resolver().resolve(students)
    source = [r.dict() for r in results]

    expected = [
        {'id': 1, 'name': 'jack', 'books': 'x' }]
    assert source == expected
