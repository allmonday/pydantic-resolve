from __future__ import annotations
from typing import List
import pytest
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend
from pydantic_resolve.util import update_forward_refs

BOOKS = {
    1: [{'name': 'book1'}, {'name': 'book2'}],
    2: [{'name': 'book3'}, {'name': 'book4'}],
    3: [{'name': 'book1'}, {'name': 'book2'}],
}
async def batch_load_fn(keys):
    books = [BOOKS.get(k, []) for k in keys]
    return books

# in reverse order

class ClassRoom(BaseModel):
    students: List[Student]

class Student(BaseModel):
    id: int
    name: str

    books: List[Book] = [] 
    def resolve_books(self, loader=LoaderDepend(batch_load_fn)):
        return loader.load(self.id)

class Book(BaseModel):
    name: str


@pytest.mark.asyncio
async def test_1():
    update_forward_refs(ClassRoom)

    students = [dict(id=1, name="jack"), dict(id=2, name="mike"), dict(id=3, name="wiki")]
    classroom = ClassRoom(students=students)
    classroom = await Resolver().resolve(classroom)
    assert isinstance(classroom.students[0].books[0], Book)

