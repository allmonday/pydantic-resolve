from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel
from pydantic_resolve.core import scan_and_store_required_fields

class Student(BaseModel):
    name: str = ''
    resolve_hello: str = ''

    def resolve_name(self):
        return '.'

    def post_name(self):
        return '.'

    zone: Optional[Zone] = None

    zeta: Optional[Zeta] = None

    def resolve_zeta(self):
        return dict(name='z')


class Zone(BaseModel):
    name: str
    qs: List[Queue]

class Queue(BaseModel):
    name: str

class Zeta(BaseModel):
    name: str


def test_get_all_fields():
    result = scan_and_store_required_fields(Student())
    assert result == {
        'test_field_pydantic.Student': {
            'resolve': ['resolve_name', 'resolve_zeta'],
            'post': ['post_name'],
            'attribute': ['zone']
        },
        'test_field_pydantic.Zone': {
            'resolve': [],
            'post': [],
            'attribute': ['qs']
        },
        'test_field_pydantic.Queue': {
            'resolve': [],
            'post': [],
            'attribute': []
        },
        'test_field_pydantic.Zeta': {
            'resolve': [],
            'post': [],
            'attribute': []
        }
    }
