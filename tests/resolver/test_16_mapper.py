from __future__ import annotations
from typing import List, Optional
import pytest
from pydantic import ConfigDict, BaseModel
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
    source = [r.model_dump() for r in results]

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
            return [[{'name': f'book-{k}'}] for k in keys ]  # return [[obj]]
    
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
    source = [r.model_dump() for r in results]

    expected = [
        {'id': 1, 'name': 'jack', 'book': [{'name': 'book-1'}] },
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
        return [Bo(name=f'book-{k}') for k in keys ]  # return [obj]
    
    class Book(BaseModel):
        name: str
        model_config = ConfigDict(from_attributes=True)

    class Student(BaseModel):
        id: int
        name: str

        book: Optional[Book] = None
        @mapper(Book)
        def resolve_book(self, loader=LoaderDepend(batch_load_fn)):
            return loader.load(self.id)

    students = [ Student(id=1, name="jack") ]
    results = await Resolver().resolve(students)
    source = [r.model_dump() for r in results]

    expected = [
        {'id': 1, 'name': 'jack', 'book': {'name': 'book-1'}},
        ]
    assert source == expected




@pytest.mark.asyncio
async def test_mapper_6():
    """
    pydantic to pydantic
    """
    class Bo(BaseModel):
        name: str

    class Book(BaseModel):
        name: str
        published: bool = False

    async def batch_load_fn(keys):
        return [[Bo(name=f'book-{k}')] for k in keys ]
    

    class Student(BaseModel):
        id: int
        name: str

        books: List[Book] = []
        @mapper(Book)
        def resolve_books(self, loader=LoaderDepend(batch_load_fn)):
            return loader.load(self.id)

    students = [ Student(id=1, name="jack") ]
    result = await Resolver().resolve(students)
    assert result[0].model_dump() == {'id':1, 'name':"jack", 'books':[{'name': "book-1", 'published':False}]}


@pytest.mark.asyncio
async def test_mapper_7():
    """
    pydantic to pydantic
    """
    class Bo(BaseModel):
        name: str

    class Book(BaseModel):
        name: str
        published: bool = False

        model_config = ConfigDict(from_attributes=True)

    async def batch_load_fn(keys):
        return [[Bo(name=f'book-{k}')] for k in keys ]
    

    class Student(BaseModel):
        id: int
        name: str

        books: List[Book] = []
        @mapper(Book)
        def resolve_books(self, loader=LoaderDepend(batch_load_fn)):
            return loader.load(self.id)

    students = [ Student(id=1, name="jack") ]
    result = await Resolver().resolve(students)
    assert result[0].model_dump() == {'id':1, 'name':"jack", 'books':[{'name': "book-1", 'published':False}]}
