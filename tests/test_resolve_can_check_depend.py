from __future__ import annotations
from typing import Tuple
import pytest
import unittest
from pydantic import BaseModel
from pydantic_resolve import resolve, LoaderDepend, DataloaderDependCantBeResolved
from aiodataloader import DataLoader

class TestDataloaderResolver(unittest.IsolatedAsyncioTestCase):

    async def test_dataloader_1(self):
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
            async def batch_load_fn(self, keys):
                counter["book"] += 1
                books = [[Book(**bb) for bb in BOOKS.get(k, [])] for k in keys]
                return books

        class Student(BaseModel):
            id: int
            name: str

            books: Tuple[Book, ...] = tuple()
            def resolve_books(self, loader=LoaderDepend(BookLoader)):
                return loader.load(self.id)

        students = [Student(id=1, name="jack"), Student(id=2, name="mike"), Student(id=3, name="wiki")]
        with pytest.raises(DataloaderDependCantBeResolved, match="DataLoader used in schema, use Resolver().resolve() instead"):
            await resolve(students)