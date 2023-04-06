from __future__ import annotations
from typing import Tuple
import pytest
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend, LoaderFieldNotProvidedError
from aiodataloader import DataLoader

@pytest.mark.asyncio
async def test_loader_depends():
    counter = {
        "book": 0
    }

    BOOKS = {
        1: [{'name': 'book1'}, {'name': 'book2'}],
        2: [{'name': 'book3'}, {'name': 'book4'}],
        3: [{'name': 'book1'}, {'name': 'book2'}],
    }

    class Book(BaseModel):
        name: str

    class BookLoader(DataLoader):
        inventory: bool
        async def batch_load_fn(self, keys):
            counter["book"] += 1
            books = [[Book(**bb) for bb in BOOKS.get(k, [])] for k in keys]
            return books

    # for testing, loder instance need to initialized inside a thread with eventloop
    # (which means it can't be put in global scope of this file)
    # otherwise it will generate anthoer loop which will raise error of
    # "task attached to another loop"

    class Student(BaseModel):
        id: int
        name: str

        books: Tuple[Book, ...] = tuple()
        def resolve_books(self, loader=LoaderDepend(BookLoader)):
            return loader.load(self.id)

    students = [Student(id=1, name="jack"), Student(id=2, name="mike"), Student(id=3, name="wiki")]
    with pytest.raises(LoaderFieldNotProvidedError):
        await Resolver().resolve(students)