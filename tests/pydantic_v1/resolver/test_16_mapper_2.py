from __future__ import annotations
from typing import List
import pytest
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend, mapper
from aiodataloader import DataLoader

class BookLoader(DataLoader):
    async def batch_load_fn(self, keys):
        return [[{'name': f'book-{k}'}] for k in keys]

class Book(BaseModel):
    name: str

class Student(BaseModel):
    id: int
    name: str

    book: List[Book] = []

    @mapper(Book)
    def resolve_book(self, loader=LoaderDepend(BookLoader)):
        return loader.load(self.id)

@pytest.mark.asyncio
async def test_mapper_2():
    """
    auto mapping: dict -> pydantic
    """

    students = [Student(id=1, name="jack")]
    results = await Resolver().resolve(students)
    source = [r.dict() for r in results]

    expected = [
        {'id': 1, 'name': 'jack', 'book': [{'name': 'book-1'}]}]
    assert source == expected

