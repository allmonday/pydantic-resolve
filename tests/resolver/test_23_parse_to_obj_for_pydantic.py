from typing import List
import pytest
from pydantic import BaseModel, ValidationError
from pydantic_resolve import Resolver, LoaderDepend, mapper

@pytest.mark.asyncio
async def test_1():
    BOOKS = {
        1: [{'name': 'book1'}, {'name': 'book2'}],
        2: [{'name': 'book3'}, {'name': 'book4'}],
        3: [{'name': 'book1'}, {'name': 'book2'}],
    }

    class Book(BaseModel):
        name: str

    async def batch_load_fn(keys):
        print('oader')
        books = [[bb for bb in BOOKS.get(k, [])] for k in keys]
        return books

    class Student(BaseModel):
        id: int
        name: str

        books: List[Book] = [] 
        def resolve_books(self, loader=LoaderDepend(batch_load_fn)):
            return loader.load(self.id)
    
    class ClassRoom(BaseModel):
        students: List[Student]


    students = [Student(id=1, name="jack"), Student(id=2, name="mike"), Student(id=3, name="wiki")]
    classroom = ClassRoom(students=students)
    classroom = await Resolver().resolve(classroom)
    assert isinstance(classroom.students[0].books[0], Book)

@pytest.mark.asyncio
async def test_2():
    BOOKS = {
        1: [{'name': 'book1'}, {'name': 'book2'}],
        2: [{'name': 'book3'}, {'name': 'book4'}],
        3: [{'name': 'book1'}, {'name': 'book2'}],
    }

    class Book(BaseModel):
        name: str
        num: int

    async def batch_load_fn(keys):
        print('oader')
        books = [[bb for bb in BOOKS.get(k, [])] for k in keys]
        return books

    class Student(BaseModel):
        id: int
        name: str

        books: List[Book] = [] 
        @mapper(lambda xx: [Book(name=x['name'], num=11) for x in xx])
        def resolve_books(self, loader=LoaderDepend(batch_load_fn)):
            return loader.load(self.id)
    
    class ClassRoom(BaseModel):
        students: List[Student]


    students = [Student(id=1, name="jack"), Student(id=2, name="mike"), Student(id=3, name="wiki")]
    classroom = ClassRoom(students=students)
    classroom = await Resolver().resolve(classroom)
    assert isinstance(classroom.students[0].books[0], Book)

@pytest.mark.asyncio
async def test_3():
    BOOKS = {
        1: [{'name': 'book1'}, {'name': 'book2'}],
        2: [{'name': 'book3'}, {'name': 'book4'}],
        3: [{'name': 'book1'}, {'name': 'book2'}],
    }

    class Book(BaseModel):
        name: str
        num: int  # missing fields

    async def batch_load_fn(keys):
        books = [[bb for bb in BOOKS.get(k, [])] for k in keys]
        return books

    class Student(BaseModel):
        id: int
        name: str

        books: List[Book] = [] 
        def resolve_books(self, loader=LoaderDepend(batch_load_fn)):
            return loader.load(self.id)
    
    class ClassRoom(BaseModel):
        students: List[Student]


    students = [Student(id=1, name="jack"), Student(id=2, name="mike"), Student(id=3, name="wiki")]
    classroom = ClassRoom(students=students)
    with pytest.raises(ValidationError):
        await Resolver().resolve(classroom)