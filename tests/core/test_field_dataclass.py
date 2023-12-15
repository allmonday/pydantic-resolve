# from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List
from pydantic_resolve.core import scan_and_store_required_fields

@dataclass
class Queue:
    name: str

@dataclass
class Zone:
    name: str
    qs: List[Queue]

@dataclass
class Zeta:
    name: str


@dataclass
class Student:
    zone: Optional[Zone] = None
    name: str = ''

    def resolve_name(self):
        return '.'

    def post_name(self):
        return '.'

    zeta: Optional[Zeta] = None

    def resolve_zeta(self):
        return dict(name='z')


def test_get_all_fields():
    result = scan_and_store_required_fields(Student())
    assert result == {
        'test_field_dataclass.Student': {
            'resolve': ['resolve_name', 'resolve_zeta'],
            'post': ['post_name'],
            'attribute': ['zone']
        },
        'test_field_dataclass.Zone': {
            'resolve': [],
            'post': [],
            'attribute': ['qs']
        },
        'test_field_dataclass.Queue': {
            'resolve': [],
            'post': [],
            'attribute': []
        },
        'test_field_dataclass.Zeta': {
            'resolve': [],
            'post': [],
            'attribute': []
        }
    }
