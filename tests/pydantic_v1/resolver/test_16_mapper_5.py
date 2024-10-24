from __future__ import annotations
from dataclasses import dataclass
from typing import List
import pytest
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend, mapper

class Bo:
    def __init__(self, name):
        self.name = name

async def batch_load_fn(keys):
    return [[Bo(name=f'book-{k}')] for k in keys]

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
async def test_mapper_5():
    """
    auto mapping fail
    """

    students = [Student(id=1, name="jack")]
    with pytest.raises(NotImplementedError):
        await Resolver().resolve(students)
