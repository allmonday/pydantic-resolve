from typing import List
import pytest
from dataclasses import dataclass, field
from pydantic_resolve import Resolver, LoaderDepend

@pytest.mark.asyncio
async def test_loader_depends_1():
    BOOKS = {
        1: [{'name': 'book1'}, {'name': 'book2'}],
        2: [{'name': 'book3'}, {'name': 'book4'}],
        3: [{'name': 'book1'}, {'name': 'book2'}],
    }

    @dataclass
    class Book():
        name: str

    async def batch_load_fn(keys):
        books = [[dict(name=bb['name']) for bb in BOOKS.get(k, [])] for k in keys]
        return books

    @dataclass
    class Student():
        id: int
        name: str

        books: List[Book] = field(default_factory=list)
        def resolve_books(self, loader=LoaderDepend(batch_load_fn)):
            return loader.load(self.id)
    
    @dataclass
    class ClassRoom():
        students: List[Student]

    students = [Student(id=1, name="jack"), Student(id=2, name="mike"), Student(id=3, name="wiki")]
    classroom = ClassRoom(students=students)
    res = await Resolver().resolve(classroom)
    assert isinstance(res.students[0].books[0], Book)
