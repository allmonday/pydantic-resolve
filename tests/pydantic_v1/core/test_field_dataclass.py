# from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List
from pydantic_resolve.analysis import scan_and_store_metadata

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
    __pydantic_resolve_expose__ = {'name': 'student_name'}
    zone: Optional[Zone] = None
    name: str = ''

    def resolve_name(self):
        return '.'

    def post_name(self):
        return '.'

    zeta2: Optional[List[Zeta]] = None
    zetas2: List[Optional[Zeta]] = field(default_factory=list)

    zeta: Optional[Zeta] = None

    def resolve_zeta(self):
        return dict(name='z')


def test_get_all_fields():
    result = scan_and_store_metadata(Student)
    expect = {
        'test_field_dataclass.Student': {
            'resolve': ['resolve_name', 'resolve_zeta'],
            'post': ['post_name'],
            'object_fields': ['zone', 'zeta2', 'zetas2'],
            'expose_dict': {'name': 'student_name'},
            'collect_dict': {},
            'has_context': False,
        },
        'test_field_dataclass.Zone': {
            'resolve': [],
            'post': [],
            'object_fields': ['qs'],
            'expose_dict': {},
            'collect_dict': {},
            'has_context': False,
        },
        'test_field_dataclass.Queue': {
            'resolve': [],
            'post': [],
            'object_fields': [],
            'expose_dict': {},
            'collect_dict': {},
            'has_context': False,
        },
        'test_field_dataclass.Zeta': {
            'resolve': [],
            'post': [],
            'object_fields': [],
            'expose_dict': {},
            'collect_dict': {},
            'has_context': False,
        }
    }
    for k, v in result.items():
        assert expect[k].items() <= v.items()