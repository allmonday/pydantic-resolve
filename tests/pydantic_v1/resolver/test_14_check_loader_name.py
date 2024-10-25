from __future__ import annotations
from typing import List
import pytest
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend
import tests.pydantic_v1.resolver.test_14_deps.mod_a as a
import tests.pydantic_v1.resolver.test_14_deps.mod_b as b

@pytest.mark.asyncio
async def test_loader_depends():
    print(a.BookLoader.__module__)
    class Student(BaseModel):
        id: int
        name: str

        a_books: List[a.Book] = [] 
        def resolve_a_books(self, loader=LoaderDepend(a.BookLoader)):
            return loader.load(self.id)

        b_books: List[b.Book] = [] 
        def resolve_b_books(self, loader=LoaderDepend(b.BookLoader)):
            return loader.load(self.id)

    students = [Student(id=1, name="jack"), Student(id=2, name="mike")]
    results = await Resolver().resolve(students)
    source = [r.dict() for r in results]
    expected = [
        {'id': 1, 'name': 'jack', 
         'a_books': [{ 'name': 'book1'}, {'name': 'book2'}],
         'b_books': [{ 'name': 'book1', 'public': 'public'}, {'name': 'book2', 'public': 'public'}]
        },
        {'id': 2, 'name': 'mike', 
         'a_books': [{ 'name': 'book3'}, {'name': 'book4'}],
         'b_books': [{ 'name': 'book3', 'public': 'public'}, {'name': 'book4', 'public': 'public'}]
        },
    ]
    assert source == expected
