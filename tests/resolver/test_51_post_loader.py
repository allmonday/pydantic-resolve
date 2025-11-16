from __future__ import annotations
from typing import List
import pytest
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend
from aiodataloader import DataLoader

BOOKS = {
    1: [{'name': 'book1'}, {'name': 'book2'}],
    2: [{'name': 'book3'}, {'name': 'book4'}],
    3: [{'name': 'book1'}, {'name': 'book2'}],
}

class Book(BaseModel):
    name: str

class BookLoader(DataLoader):
    async def batch_load_fn(self, keys) -> List[List[Book]]:
        books = [[Book(**bb) for bb in BOOKS.get(k, [])] for k in keys]
        return books

class Student(BaseModel):
    id: int
    name: str

    books: List[Book] = []
    def post_books(self, loader=LoaderDepend(BookLoader)):
        return loader.load(self.id)


@pytest.mark.asyncio
async def test_loader_depends():
    # post can support dataloader
    students = [Student(id=1, name="jack"), Student(id=2, name="mike"), Student(id=3, name="wiki")]
    result = await Resolver().resolve(students)

    assert result == [
        Student(id=1, name='jack', books=[Book(name='book1'), Book(name='book2')]),
        Student(id=2, name='mike', books=[Book(name='book3'), Book(name='book4')]),
        Student(id=3, name='wiki', books=[Book(name='book1'), Book(name='book2')]),
    ]