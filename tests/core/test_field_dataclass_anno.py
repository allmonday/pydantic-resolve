from dataclasses import dataclass
from typing import Optional, List
from pydantic_resolve.core import scan_and_store_metadata

@dataclass
class Student:
    __pydantic_resolve_expose__ = {'name': 'student_name'}
    zone: Optional['Zone'] = None
    name: str = ''

    def resolve_name(self):
        return '.'

    def post_name(self):
        return '.'

    zeta: Optional['Zeta'] = None

    def resolve_zeta(self):
        return dict(name='z')

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


def test_get_all_fields():
    result = scan_and_store_metadata(Student)
    assert result == {
        'test_field_dataclass_anno.Student': {
            'resolve': ['resolve_name', 'resolve_zeta'],
            'post': ['post_name'],
            'attribute': ['zone'],
            'expose_dict': {'name': 'student_name'},
            'collect_dict': {}
        },
        'test_field_dataclass_anno.Zone': {
            'resolve': [],
            'post': [],
            'attribute': ['qs'],
            'expose_dict': {},
            'collect_dict': {}
        },
        'test_field_dataclass_anno.Queue': {
            'resolve': [],
            'post': [],
            'attribute': [],
            'expose_dict': {},
            'collect_dict': {}
        },
        'test_field_dataclass_anno.Zeta': {
            'resolve': [],
            'post': [],
            'attribute': [],
            'expose_dict': {},
            'collect_dict': {}
        }
    }
