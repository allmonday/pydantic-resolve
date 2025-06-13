from typing import List
import pytest
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend

BOOKS = {
    1: [{'name': 'book1'}, {'name': 'book2'}],
    2: [{'name': 'book3'}, {'name': 'book4'}],
    3: [{'name': 'book1'}, {'name': 'book2'}],
}

class Book(BaseModel):
    name: str

async def batch_load_fn(keys):
    books = [[Book(**bb) for bb in BOOKS.get(k, [])] for k in keys]
    return books

class Student(BaseModel):
    id: int
    name: str

    books: List[Book] = []

    def resolve_books(self, loader=LoaderDepend(batch_load_fn)):
        return loader.load(self.id)

class ClassRoom(BaseModel):
    students: List[Student]

@pytest.mark.asyncio
async def test_loader_depends():
    students = [Student(id=1, name="jack"), Student(id=2, name="mike"), Student(id=3, name="wiki")]
    classroom = ClassRoom(students=students)
    res = await Resolver().resolve(classroom)
    source = res.dict()
    expected = {
        "students": [
            {'id': 1, 'name': 'jack', 'books': [{ 'name': 'book1'}, {'name': 'book2'}]},
            {'id': 2, 'name': 'mike', 'books': [{ 'name': 'book3'}, {'name': 'book4'}]},
            {'id': 3, 'name': 'wiki', 'books': [{ 'name': 'book1'}, {'name': 'book2'}]}]}
    assert source == expected

