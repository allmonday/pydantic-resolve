from __future__ import annotations
from typing import List
import pytest
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend, mapper

class Bo:
    def __init__(self, name):
        self.name = name

async def batch_load_fn(keys):
    return [Bo(name=f'book-{k}') for k in keys]

class Book(BaseModel):
    name: str

    class Config:
        orm_mode = True

class Student(BaseModel):
    id: int
    name: str

    book: List[Book] = []

    @mapper(Book)
    def resolve_book(self, loader=LoaderDepend(batch_load_fn)):
        return loader.load(self.id)

@pytest.mark.asyncio
async def test_mapper_3():
    """
    auto mapping: obj -> pydantic
    """
    students = [Student(id=1, name="jack")]
    results = await Resolver().resolve(students)
    source = [r.dict() for r in results]

    expected = [
        {'id': 1, 'name': 'jack', 'book': {'name': 'book-1'}}]
    assert source == expected
