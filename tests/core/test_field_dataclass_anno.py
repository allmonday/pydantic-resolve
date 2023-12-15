from dataclasses import dataclass
from typing import Optional, List
from pydantic_resolve.core import get_all_fields

@dataclass
class Student:
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
    result = get_all_fields(Student())
    assert result == {
        'test_field_dataclass_anno.Student': {
            'resolve': ['resolve_name', 'resolve_zeta'],
            'post': ['post_name'],
            'attribute': ['zone']
        },
        'test_field_dataclass_anno.Zone': {
            'resolve': [],
            'post': [],
            'attribute': ['qs']
        },
        'test_field_dataclass_anno.Queue': {
            'resolve': [],
            'post': [],
            'attribute': []
        },
        'test_field_dataclass_anno.Zeta': {
            'resolve': [],
            'post': [],
            'attribute': []
        }
    }
