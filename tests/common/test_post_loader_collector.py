from __future__ import annotations
from typing import List
import pytest
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend, Collector
from aiodataloader import DataLoader

BOOKS = {
    1: [{'name': 'book1'}, {'name': 'book2'}],
    2: [{'name': 'book3'}, {'name': 'book4'}],
    3: [{'name': 'book1'}, {'name': 'book2'}],
}

class Book(BaseModel):
    __pydantic_resolve_collect__ = {'name': 'name_collector'}

    name: str
    def resolve_name(self):
        return 'hello_' + self.name

class BookLoader(DataLoader):
    async def batch_load_fn(self, keys) -> List[List[Book]]:
        books = [[Book(**bb) for bb in BOOKS.get(k, [])] for k in keys]
        return books

class Student(BaseModel):
    id: int
    name: str

    books: List[Book] = []
    def post_books(self, loader=LoaderDepend(BookLoader)):
        return loader.load(self.id)
    
    book_names_a: List[str] = []
    def post_book_names_a(self, collector=Collector('name_collector')):  # will not work. post method are concurrently executed.
        return collector.values()
    
    book_names: List[str] = []
    def post_default_handler(self, collector=Collector('name_collector')): 
        self.book_names = collector.values()

@pytest.mark.asyncio
async def test_post_loader_collect_exception():
    """
    return type defined in post_method can be recursively traversed
    but the other post_method wont be able to collect from descendant
    """
    students = [Student(id=1, name="jack"), Student(id=2, name="mike"), Student(id=3, name="wiki")]
    result = await Resolver().resolve(students)

    assert result == [
        Student(id=1, name='jack', books=[Book(name='hello_book1'), Book(name='hello_book2')], book_names=['hello_book1', 'hello_book2'], book_names_a=[]),
        Student(id=2, name='mike', books=[Book(name='hello_book3'), Book(name='hello_book4')], book_names=['hello_book3', 'hello_book4'], book_names_a=[]),
        Student(id=3, name='wiki', books=[Book(name='hello_book1'), Book(name='hello_book2')], book_names=['hello_book1', 'hello_book2'], book_names_a=[]),
    ]