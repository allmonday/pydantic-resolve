from __future__ import annotations
from operator import is_
from typing import Tuple
import unittest
import asyncio
from pydantic import BaseModel
from pydantic_resolve import resolver
from dataclasses import dataclass, asdict

class Student(BaseModel):
    name: str
    intro: str = ''
    def resolve_intro(self):
        return f'hello {self.name}'
    
    books: tuple[Book, ...] = tuple()
    async def resolve_books(self):
        return await get_books()

async def get_books():
    await asyncio.sleep(1)
    return [Book(name="sky"), Book(name="sea")]

class Book(BaseModel):
    name: str

class TestResolver(unittest.IsolatedAsyncioTestCase):

    async def test_resolver_1(self):
        stu = Student(name="boy")
        result = await resolver(stu)
        expected = {
            'name': 'boy',
            'intro': 'hello boy',
            'books': [{'name': 'sky'}, {'name': 'sea'}]
        }
        self.assertEqual(result.dict(), expected)

    async def test_resolver_2(self):
        stu = [Student(name="boy")]
        result = await resolver(stu)
        expected = {
            'name': 'boy',
            'intro': 'hello boy',
            'books': [{'name': 'sky'}, {'name': 'sea'}]
        }
        self.assertEqual(result[0].dict(), expected)

    async def test_schema(self):
        Student.update_forward_refs(Book=Book)
        schema = Student.schema_json()
        expected = '''{"title": "Student", "type": "object", "properties": {"name": {"title": "Name", "type": "string"}, "intro": {"title": "Intro", "default": "", "type": "string"}, "books": {"title": "Books", "default": [], "type": "array", "items": {"$ref": "#/definitions/Book"}}}, "required": ["name"], "definitions": {"Book": {"title": "Book", "type": "object", "properties": {"name": {"title": "Name", "type": "string"}}, "required": ["name"]}}}'''
        self.assertEqual(schema, expected)


@dataclass
class Wheel:
    is_ok: bool 

@dataclass
class Car:
    name: str
    wheels: Tuple[Wheel, ...] = tuple()

    async def resolve_wheels(self):
        await asyncio.sleep(1)
        return [Wheel(is_ok=True)]

class TestDataclassResolver(unittest.IsolatedAsyncioTestCase):

    async def test_resolver_1(self):
        car = Car(name="byd")
        result = await resolver(car)
        expected = {
            'name': 'byd',
            'wheels': [{'is_ok': True}]
        }
        self.assertEqual(asdict(result), expected)

    async def test_resolver_2(self):
        car = [Car(name="byd")]
        result = await resolver(car)
        expected = {
            'name': 'byd',
            'wheels': [{'is_ok': True}]
        }
        self.assertEqual(asdict(result[0]), expected)


