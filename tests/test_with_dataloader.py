from __future__ import annotations
from typing import Tuple
import unittest
from pydantic import BaseModel
from pydantic_resolve import resolve
from aiodataloader import DataLoader

class TestDataloaderResolver(unittest.IsolatedAsyncioTestCase):
    async def test_dataloader_1(self):

        BOOKS = {
            1: [{'name': 'book1'}, {'name': 'book2'}],
            2: [{'name': 'book3'}, {'name': 'book4'}],
        }

        class Book(BaseModel):
            name: str

        class BookLoader(DataLoader):
            async def batch_load_fn(self, keys):
                books = [[Book(**bb) for bb in BOOKS.get(k, [])] for k in keys]
                return books

        # for testing, loder instance need to initialized inside a thread with eventloop
        # (which means it can't be put in global scope of this file)
        # otherwise it will generate anthoer loop which will raise error of
        # "task attached to another loop"
        book_loader = BookLoader()  

        class Student(BaseModel):
            id: int
            name: str

            books: Tuple[Book, ...] = tuple()
            def resolve_books(self):
                return book_loader.load(self.id)

        students = [Student(id=1, name="jack"), Student(id=2, name="mike")]
        results = await resolve(students)
        source = [r.dict() for r in results]
        expected = [
            {'id': 1, 'name': 'jack', 'books': [{ 'name': 'book1'}, {'name': 'book2'}]},
            {'id': 2, 'name': 'mike', 'books': [{ 'name': 'book3'}, {'name': 'book4'}]},
        ]
        self.assertEqual(source, expected)

    async def test_dataloader_2(self):

        BOOKS = {
            1: [{'name': 'book1'}, {'name': 'book2'}],
            2: [{'name': 'book3'}, {'name': 'book4'}],
        }
        AUTHORS = {
            'book1': [{'name': 'book1-author'}],
            'book2': [{'name': 'book2-author'}]
        }

        class BookLoader(DataLoader):
            async def batch_load_fn(self, keys):
                books = [[Book(**bb) for bb in BOOKS.get(k, [])] for k in keys]
                return books

        class AuthorLoader(DataLoader):
            async def batch_load_fn(self, keys):
                authors = [[Author(**aa) for aa in AUTHORS.get(k, [])] for k in keys]
                return authors


        class Author(BaseModel):
            name: str

        class Book(BaseModel):
            name: str
            authors: Tuple[Author, ...] = tuple()

            def resolve_authors(self):
                return author_loader.load(self.name)

        book_loader = BookLoader()  
        author_loader = AuthorLoader()  

        class Student(BaseModel):
            id: int
            name: str

            books: Tuple[Book, ...] = tuple()
            def resolve_books(self):
                return book_loader.load(self.id)

        students = [Student(id=1, name="jack"), Student(id=2, name="mike")]
        results = await resolve(students)
        source = [r.dict() for r in results]
        expected = [
            {'id': 1, 'name': 'jack', 'books': [
                { 'name': 'book1', 'authors': [{'name': 'book1-author'}]},
                { 'name': 'book2', 'authors': [{'name': 'book2-author'}]}
            ]},
            {'id': 2, 'name': 'mike', 'books': [{ 'name': 'book3', 'authors': []}, {'name': 'book4', 'authors': []}]},
        ]
        self.assertEqual(source, expected)
