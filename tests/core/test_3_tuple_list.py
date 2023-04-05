from __future__ import annotations
from typing import List, Tuple
import asyncio
from pydantic import BaseModel
from pydantic_resolve import resolve
import pytest

class Student(BaseModel):
    new_books: List[str] = []    
    async def resolve_new_books(self):
        await asyncio.sleep(1)
        return ['book1', 'book2']

    old_books: Tuple[str, ...] = tuple()    
    async def resolve_old_books(self):
        await asyncio.sleep(1)
        return ['book1', 'book2']


@pytest.mark.asyncio
async def test_type_definition():
    stu = Student()
    result = await resolve(stu)
    expected = {
        'new_books': ['book1', 'book2'],
        'old_books': ['book1', 'book2']
    }
    assert result.dict() == expected
