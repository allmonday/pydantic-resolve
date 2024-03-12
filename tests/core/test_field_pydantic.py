from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel
from pydantic_resolve.core import scan_and_store_metadata

class Student(BaseModel):
    __pydantic_resolve_expose__ = {'name': 'student_name'}
    name: str = ''
    resolve_hello: str = ''

    def resolve_name(self):
        return '.'

    def post_name(self):
        return '.'

    zones: List[Optional[Zone]] = [None]
    zones2: List[Zone] = []
    zone: Optional[Optional[Zone]] = None
    z: str # ignored in attributes

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
    result = scan_and_store_metadata(Student)
    assert result == {
        'test_field_pydantic.Student': {
            'resolve': ['resolve_name', 'resolve_zeta'],
            'post': ['post_name'],
            'attribute': ['zones', 'zones2', 'zone'],
            'expose_dict': {'name': 'student_name'},
            'collect_dict': {}
        },
        'test_field_pydantic.Zone': {
            'resolve': [],
            'post': [],
            'attribute': ['qs'],
            'expose_dict': {},
            'collect_dict': {}
        },
        'test_field_pydantic.Queue': {
            'resolve': [],
            'post': [],
            'attribute': [],
            'expose_dict': {},
            'collect_dict': {}
        },
        'test_field_pydantic.Zeta': {
            'resolve': [],
            'post': [],
            'attribute': [],
            'expose_dict': {},
            'collect_dict': {}
        }
    }
