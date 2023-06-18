from __future__ import annotations
from dataclasses import dataclass
from typing import List
import pytest
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend, mapper
from aiodataloader import DataLoader

@pytest.mark.asyncio
async def test_mapper():
    """
    user provided mapper
    """
    class BookLoader(DataLoader):
        async def batch_load_fn(self, keys):
            return keys 

    class Student(BaseModel):
        id: int
        name: str

        books: str = ''
        @mapper(lambda x: str(x))
        def resolve_books(self, loader=LoaderDepend(BookLoader)):
            return loader.load(self.id)

    students = [
        Student(id=1, name="jack"),
        Student(id=2, name="jack")
        ]
    results = await Resolver().resolve(students)
    source = [r.dict() for r in results]

    expected = [
        {'id': 1, 'name': 'jack', 'books': '1' },
        {'id': 2, 'name': 'jack', 'books': '2' }
        ]
    assert source == expected


@pytest.mark.asyncio
async def test_mapper_2():
    """
    auto mapping: dict -> pydantic
    """

    class BookLoader(DataLoader):
        async def batch_load_fn(self, keys):
            return [{'name': f'book-{k}'} for k in keys ]
    
    class Book(BaseModel):
        name: str

    class Student(BaseModel):
        id: int
        name: str

        book: List[Book] = []
        @mapper(Book)
        def resolve_book(self, loader=LoaderDepend(BookLoader)):
            return loader.load(self.id)

    students = [ Student(id=1, name="jack") ]
    results = await Resolver().resolve(students)
    source = [r.dict() for r in results]

    expected = [
        {'id': 1, 'name': 'jack', 'book': {'name': 'book-1'} },
        ]
    assert source == expected


@pytest.mark.asyncio
async def test_mapper_3():
    """
    auto mapping: obj -> pydantic
    """
    class Bo:
        def __init__(self, name):
            self.name = name

    async def batch_load_fn(keys):
        return [Bo(name=f'book-{k}') for k in keys ]
    
    class Book(BaseModel):
        name: str
        class Config:
            orm_mode=True

    class Student(BaseModel):
        id: int
        name: str

        book: List[Book] = []
        @mapper(Book)
        def resolve_book(self, loader=LoaderDepend(batch_load_fn)):
            return loader.load(self.id)

    students = [ Student(id=1, name="jack") ]
    results = await Resolver().resolve(students)
    source = [r.dict() for r in results]

    expected = [
        {'id': 1, 'name': 'jack', 'book': {'name': 'book-1'} },
        ]
    assert source == expected


@pytest.mark.asyncio
async def test_mapper_4():
    """
    auto mapping: dict -> dataclass
    """

    async def batch_load_fn(keys):
        return [{'name': f'book-{k}'} for k in keys ]
    
    @dataclass
    class Book:
        name: str

    class Student(BaseModel):
        id: int
        name: str

        book: List[Book] = []
        @mapper(Book)
        def resolve_book(self, loader=LoaderDepend(batch_load_fn)):
            return loader.load(self.id)

    students = [ Student(id=1, name="jack") ]
    results = await Resolver().resolve(students)
    source = [r.dict() for r in results]

    expected = [
        {'id': 1, 'name': 'jack', 'book': Book(name='book-1')},
        ]
    assert source == expected


@pytest.mark.asyncio
async def test_mapper_5():
    """
    auto mapping fail
    """
    class Bo:
        def __init__(self, name):
            self.name = name

    async def batch_load_fn(keys):
        return [Bo(name=f'book-{k}') for k in keys ]
    
    @dataclass
    class Book:
        name: str

    class Student(BaseModel):
        id: int
        name: str

        book: List[Book] = []
        @mapper(Book)
        def resolve_book(self, loader=LoaderDepend(batch_load_fn)):
            return loader.load(self.id)

    students = [ Student(id=1, name="jack") ]
    with pytest.raises(NotImplementedError):
        await Resolver().resolve(students)
