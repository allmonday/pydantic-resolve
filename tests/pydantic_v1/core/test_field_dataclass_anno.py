from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List
from pydantic_resolve.analysis import Analytic
from pydantic_resolve import LoaderDepend, Collector


async def loader_fn(keys):
    return keys


@dataclass
class Student:
    __pydantic_resolve_expose__ = {'name': 'student_name'}
    zone: Optional[Zone] = None

    name: str = ''
    def resolve_name(self, context, ancestor_context, loader=LoaderDepend(loader_fn)):
        return '.'

    def post_name(self):
        return '.'

    zeta: Optional[Zeta] = None

    def resolve_zeta(self):
        return dict(name='z')
    
    queue_names: List[str] = field(default_factory=list)
    def post_queue_names(self, collector=Collector('queue_name')):
        return collector.values()

@dataclass
class Queue:
    __pydantic_resolve_collect__ = {"name": "queue_name"}
    name: str

@dataclass
class Zone:
    name: str
    qs: List[Queue]

@dataclass
class Zeta:
    name: str


def test_get_all_fields():
    """
    post params is not included
    """
    result = Analytic().scan(Student)
    expect = {
        'test_field_dataclass_anno.Student': {
            'resolve': ['resolve_name', 'resolve_zeta'],
            'post': ['post_name', 'post_queue_names'],
            'object_fields': ['zone'],
            'expose_dict': {'name': 'student_name'},
            'collect_dict': {},
            'kls': Student,
            'resolve_params': {
                'resolve_name': {
                    'trim_field': 'name',
                    'context': True,
                    'ancestor_context': True,
                    'parent': False,
                    'dataloaders': [
                        {
                            'param': 'loader',
                            'kls': loader_fn,
                            'path': 'test_field_dataclass_anno.loader_fn',
                            'request_type': None
                        }
                    ],
                }, 
                'resolve_zeta': {
                    'trim_field': 'zeta',
                    'context': False,
                    'ancestor_context': False,
                    'parent': False,
                    'dataloaders': [],
                }
            },
        },
        'test_field_dataclass_anno.Zone': {
            'resolve': [],
            'post': [],
            'object_fields': ['qs'],
            'expose_dict': {},
            'collect_dict': {},
            'kls': Zone
        },
        'test_field_dataclass_anno.Queue': {
            'resolve': [],
            'post': [],
            'object_fields': [],
            'expose_dict': {},
            'collect_dict': {'name': 'queue_name'},
            'kls': Queue
        },
        'test_field_dataclass_anno.Zeta': {
            'resolve': [],
            'post': [],
            'object_fields': [],
            'expose_dict': {},
            'collect_dict': {},
            'kls': Zeta
        }
    }
    for k, v in result.items():
        assert expect[k].items() <= v.items()
