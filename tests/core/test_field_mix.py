from __future__ import annotations
from typing import List
from pydantic import BaseModel
from pydantic_resolve.analysis import Analytic

class Book(BaseModel):
    name: str

class Student(BaseModel):
    __pydantic_resolve_expose__ = {'name': 's_name'}
    name: str = ''

    books: List[Book] = []

    def resolve_books(self):
        return []


def test_get_all_fields():
    result = Analytic().scan(Student)
    expect = {
        'test_field_mix.Student': {
            'resolve': ['resolve_books'],
            'post': [],
            'object_fields': [],
            'expose_dict': {'name': 's_name'},
            'collect_dict': {}
        },
        'test_field_mix.Book': {
            'resolve': [],
            'post': [],
            'object_fields': [],
            'expose_dict': {},
            'collect_dict': {}
        },
    }
    for k, v in result.items():
        assert expect[k].items() <= v.items()