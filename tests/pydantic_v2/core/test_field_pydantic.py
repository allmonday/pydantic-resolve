from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel
from pydantic_resolve.analysis import scan_and_store_metadata, convert_metadata_key_as_kls
from pydantic_resolve import LoaderDepend

async def loader_fn(keys):
    return keys

class Student(BaseModel):
    __pydantic_resolve_expose__ = {'name': 'student_name'}
    name: str = ''
    resolve_hello: str = ''

    def resolve_name(self, context, ancestor_context, loader=LoaderDepend(loader_fn)):
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
    expect = {
        'test_field_pydantic.Student': {
            'resolve': ['resolve_name', 'resolve_zeta'],
            'post': ['post_name'],
            'object_fields': ['zones', 'zones2', 'zone'],
            'expose_dict': {'name': 'student_name'},
            'collect_dict': {}
            # ... others
        },
        'test_field_pydantic.Zone': {
            'resolve': [],
            'post': [],
            'object_fields': ['qs'],
            'expose_dict': {},
            'collect_dict': {}
            # ... others
        },
        'test_field_pydantic.Queue': {
            'resolve': [],
            'post': [],
            'object_fields': [],
            'expose_dict': {},
            'collect_dict': {}
            # ... others
        },
        'test_field_pydantic.Zeta': {
            'resolve': [],
            'post': [],
            'object_fields': [],
            'expose_dict': {},
            'collect_dict': {}
            # ... others
        }
    }
    for k, v in result.items():
        assert expect[k].items() <= v.items()


def test_convert_metadata():
    result = scan_and_store_metadata(Student)
    result = convert_metadata_key_as_kls(result)
    expect = {
        Student: {
            'resolve': ['resolve_name', 'resolve_zeta'],
            'post': ['post_name'],
            'object_fields': ['zones', 'zones2', 'zone'],
            'expose_dict': {'name': 'student_name'},
            'collect_dict': {},
            'kls': Student,
            'kls_path': 'test_field_pydantic.Student',
            # ... others
        },
        Zone: {
            'resolve': [],
            'post': [],
            'object_fields': ['qs'],
            'expose_dict': {},
            'collect_dict': {},
            'kls': Zone,
            'kls_path': 'test_field_pydantic.Zone',
            # ... others
        },
        Queue: {
            'resolve': [],
            'post': [],
            'object_fields': [],
            'expose_dict': {},
            'collect_dict': {},
            'kls': Queue,
            'kls_path': 'test_field_pydantic.Queue',
            # ... others
        },
        Zeta: {
            'resolve': [],
            'post': [],
            'object_fields': [],
            'expose_dict': {},
            'collect_dict': {},
            'kls': Zeta,
            'kls_path': 'test_field_pydantic.Zeta',
            # ... others
        }
    }
    for k, v in result.items():
        assert expect[k].items() <= v.items()


def test_resolve_params():
    result = scan_and_store_metadata(Student)
    expect = {
        'test_field_pydantic.Student': {
            # ... others
            'has_context': True,
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
                            'path': 'test_field_pydantic.loader_fn'
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
        }
    }
    key = 'test_field_pydantic.Student'
    assert expect[key].items() <= result[key].items()