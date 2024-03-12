from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List
from pydantic import BaseModel
from pydantic_resolve.core import scan_and_store_metadata

@dataclass
class Book:
    name: str

class Student(BaseModel):
    name: str = ''

    books: List[Book] = []

    def resolve_books(self):
        return []


def test_get_all_fields():
    result = scan_and_store_metadata(Student)
    assert result == {
        'test_field_mix.Student': {
            'resolve': ['resolve_books'],
            'post': [],
            'attribute': []
        },
        'test_field_mix.Book': {
            'resolve': [],
            'post': [],
            'attribute': []
        },
    }
