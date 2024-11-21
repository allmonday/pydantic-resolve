from __future__ import annotations
from typing import List
import asyncio
from pydantic import BaseModel
from pydantic_resolve import Resolver
import pytest

class Student(BaseModel):
    name: str
    intro: str = ''
    def resolve_intro(self) -> str:
        return f'hello {self.name}'

    books: List[str] = []    
    async def resolve_books(self) -> List[str]:
        await asyncio.sleep(0.1)
        return ['book1', 'book2']


@pytest.mark.asyncio
async def test_resolve_object():
    stu = Student(name="martin")
    result = await Resolver().resolve(stu)
    expected = {
        'name': 'martin',
        'intro': 'hello martin',
        'books': ['book1', 'book2']
    }
    assert result.dict() == expected

@pytest.mark.asyncio
async def test_resolve_array():
    stu = [Student(name="martin")]
    results = await Resolver().resolve(stu)
    results = [r.dict() for r in results]
    expected = [{
        'name': 'martin',
        'intro': 'hello martin',
        'books': ['book1', 'book2']
    }]
    assert results == expected

def test_schema():
    schema = Student.schema_json()
    expected = '''{"title": "Student", "type": "object", "properties": {"name": {"title": "Name", "type": "string"}, "intro": {"title": "Intro", "default": "", "type": "string"}, "books": {"title": "Books", "default": [], "type": "array", "items": {"type": "string"}}}, "required": ["name"]}'''
    assert schema == expected