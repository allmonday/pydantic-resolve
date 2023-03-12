# Pydantic-resolve

```python
import asyncio
from pydantic import BaseModel
from pydantic_resolve import resolve

class Student(BaseModel):
    name: str
    greet: str = ''
    async def resolve_greet(self):
        await asyncio.sleep(1)  # mock i/o
        return f'hello {self.name}'

async def main():
    students = [Student(name='john' )]
    results = await resolve(students)
    print(results)

asyncio.run(main())

# output: [Student(name='john', greet='hello john')]
```

- Pydantic-resolve helps you asynchoronously, resursively resolve a pydantic object (or dataclass object)

- Pydantic-resolve, when used in conjunction with aiodataloader, allows you to easily generate nested data structures without worrying about generating N+1 queries.

- inspired by [graphene](https://graphene-python.org/)

[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
![Test Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/allmonday/6f1661c6310e1b31c9a10b0d09d52d11/raw/covbadge.json)
## Install

```shell
pip install pydantic-resolve
```

## Demo 1, Resolve asynchoronously

```python
from pydantic_resolve import resolve

class Book(BaseModel):
    name: str

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

class TestResolver(unittest.IsolatedAsyncioTestCase):

    async def test_resolver_1(self):
        stu = Student(name="boy")
        result = await resolve(stu)
        expected = {
            'name': 'boy',
            'intro': 'hello boy',
            'books': [{'name': 'sky'}, {'name': 'sea'}]
        }
        self.assertEqual(result.dict(), expected)

    async def test_resolver_2(self):
        stu = [Student(name="boy")]
        result = await resolve(stu)
        expected = {
            'name': 'boy',
            'intro': 'hello boy',
            'books': [{'name': 'sky'}, {'name': 'sea'}]
        }
        self.assertEqual(result[0].dict(), expected)

    async def test_schema(self):
        # Student.update_forward_refs(Book=Book)
        schema = Student.schema_json()
        expected = '''{"title": "Student", "type": "object", "properties": {"name": {"title": "Name", "type": "string"}, "intro": {"title": "Intro", "default": "", "type": "string"}, "books": {"title": "Books", "default": [], "type": "array", "items": {"$ref": "#/definitions/Book"}}}, "required": ["name"], "definitions": {"Book": {"title": "Book", "type": "object", "properties": {"name": {"title": "Name", "type": "string"}}, "required": ["name"]}}}'''
        self.assertEqual(schema, expected)
```

### Demo 2: Integrated with aiodataloader:

```python
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
```

## Unittest

```shell
poetry run python -m unittest  # or
poetry run pytest  # or
poetry run tox
```

## Coverage 

```shell
poetry run coverage run -m pytest
poetry run coverage report -m
```
