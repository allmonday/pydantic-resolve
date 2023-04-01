from __future__ import annotations
from typing import List
import unittest
import asyncio
from pydantic import BaseModel
from pydantic_resolve import resolve

class Book(BaseModel):
    name: str

class Student(BaseModel):
    name: str
    intro: str = ''
    def resolve_intro(self):
        return f'hello {self.name}'
    
    books: List[Book] = []
    async def resolve_books(self):
        return await get_books()

async def get_books():
    await asyncio.sleep(1)
    return [Book(name="sky"), Book(name="sea")]

class TestResolver(unittest.IsolatedAsyncioTestCase):

    async def test_resolver(self):
        stu = [Student(name="martin")]
        result = await resolve(stu)
        expected = {
            'name': 'martin',
            'intro': 'hello martin',
            'books': [{'name': 'sky'}, {'name': 'sea'}]
        }
        self.assertEqual(result[0].dict(), expected)