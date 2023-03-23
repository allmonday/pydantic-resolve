from __future__ import annotations
from typing import Tuple
import unittest
import asyncio
from pydantic import BaseModel
from pydantic_resolve import resolve
from dataclasses import dataclass, asdict

class Book(BaseModel):
    name: str

class Student(BaseModel):
    name: str
    intro: str = ''
    def resolve_intro(self):
        return f'hello {self.name}'
    
    books: Tuple[Book, ...] = tuple()
    async def resolve_books(self):
        return await get_books()

async def get_books():
    await asyncio.sleep(1)
    return [Book(name="sky"), Book(name="sea")]

class TestResolverWithTuple(unittest.IsolatedAsyncioTestCase):

    async def test_resolver_1(self):
        stu = (Student(name="john"), Student(name="mike"))
        result = await resolve(stu)
        expected_1 = {
            'name': 'john',
            'intro': 'hello john',
            'books': [{'name': 'sky'}, {'name': 'sea'}]
        }
        expected_2 = {
            'name': 'mike',
            'intro': 'hello mike',
            'books': [{'name': 'sky'}, {'name': 'sea'}]
        }
        self.assertEqual(result[0].dict(), expected_1)
        self.assertEqual(result[1].dict(), expected_2)
