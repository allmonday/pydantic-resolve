from __future__ import annotations
from typing import List
import pytest
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend, mapper
from aiodataloader import DataLoader

@pytest.mark.asyncio
async def test_loader_depends():
    class BookLoader(DataLoader):
        async def batch_load_fn(self, keys):
            return keys 

    class Student(BaseModel):
        id: int
        name: str

        books: List[str] = []
        @mapper(lambda x: str(x))
        def resolve_books(self, loader=LoaderDepend(BookLoader)):
            return loader.load(self.id)

    students = [
        Student(id=1, name="jack"),
        Student(id=2, name="jack")
        ]
    results = await Resolver().resolve(students)
    source = [r.dict() for r in results]

    expected = [
        {'id': 1, 'name': 'jack', 'books': '1' },
        {'id': 2, 'name': 'jack', 'books': '2' }
        ]
    assert source == expected
