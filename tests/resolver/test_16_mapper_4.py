from __future__ import annotations
from dataclasses import dataclass
from typing import List
import pytest
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend, mapper

async def batch_load_fn(keys):
    return [[{'name': f'book-{k}'}] for k in keys]

@dataclass
class Book:
    name: str

class Student(BaseModel):
    id: int
    name: str

    book: List[Book] = []

    @mapper(Book)
    def resolve_book(self, loader=LoaderDepend(batch_load_fn)):
        return loader.load(self.id)

@pytest.mark.asyncio
async def test_mapper_4():
    """
    auto mapping: dict -> dataclass
    """
    students = [Student(id=1, name="jack")]
    results = await Resolver().resolve(students)
    source = [r.dict() for r in results]

    expected = [
        {'id': 1, 'name': 'jack', 'book': [Book(name='book-1')]}]
    assert source == expected
