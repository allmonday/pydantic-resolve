from __future__ import annotations
from dataclasses import dataclass
from typing import List
import pytest
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend, mapper
from aiodataloader import DataLoader

class Bo(BaseModel):
    name: str

class Book(BaseModel):
    name: str
    published: bool = False

async def batch_load_fn(keys):
    return [[Bo(name=f'book-{k}')] for k in keys]


class Student(BaseModel):
    id: int
    name: str

    books: List[Book] = []

    @mapper(Book)
    def resolve_books(self, loader=LoaderDepend(batch_load_fn)):
        return loader.load(self.id)

@pytest.mark.asyncio
async def test_mapper_6():
    """
    pydantic to pydantic
    """

    students = [Student(id=1, name="jack")]
    result = await Resolver().resolve(students)
    assert result[0].dict() == {'id': 1, 'name': "jack", 'books': [{'name': "book-1", 'published': False}]}
