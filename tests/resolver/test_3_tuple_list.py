from __future__ import annotations
from typing import List
import asyncio
from pydantic import BaseModel
from pydantic_resolve import Resolver
import pytest

class Student(BaseModel):
    new_books: List[str] = []    
    async def resolve_new_books(self) -> List[str]:
        await asyncio.sleep(.1)
        return ['book1', 'book2']

    old_books: List[str] = []    
    async def resolve_old_books(self) -> List[str]:
        await asyncio.sleep(.1)
        return ['book1', 'book2']


@pytest.mark.asyncio
async def test_type_definition():
    stu = Student()
    result = await Resolver().resolve(stu)
    expected = {
        'new_books': ['book1', 'book2'],
        'old_books': ['book1', 'book2']
    }
    assert result.model_dump() == expected
