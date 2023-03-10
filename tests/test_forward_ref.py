from typing import Tuple
import unittest
import asyncio
from pydantic import BaseModel

class Student(BaseModel):
    name: str
    intro: str = ''
    def resolve_intro(self):
        return f'hello {self.name}'
    
    books: Tuple['Book', ...] = tuple()
    async def resolve_books(self):
        return await get_books()

async def get_books():
    await asyncio.sleep(1)
    return [Book(name="sky"), Book(name="sea")]

class Book(BaseModel):
    name: str

class TestResolver(unittest.IsolatedAsyncioTestCase):
    async def test_schema(self):
        Student.update_forward_refs(Book=Book)
        schema = Student.schema_json()
        expected = '''{"title": "Student", "type": "object", "properties": {"name": {"title": "Name", "type": "string"}, "intro": {"title": "Intro", "default": "", "type": "string"}, "books": {"title": "Books", "default": [], "type": "array", "items": {"$ref": "#/definitions/Book"}}}, "required": ["name"], "definitions": {"Book": {"title": "Book", "type": "object", "properties": {"name": {"title": "Name", "type": "string"}}, "required": ["name"]}}}'''
        self.assertEqual(schema, expected)
