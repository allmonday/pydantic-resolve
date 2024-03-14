from __future__ import annotations
import pytest
from typing import Optional, List
from pydantic import BaseModel
from aiodataloader import DataLoader
from pydantic_resolve.core import scan_and_store_metadata, _validate_and_create_instance
from pydantic_resolve import LoaderDepend, LoaderFieldNotProvidedError

async def loader_fn(keys):
    return keys

class MyLoader(DataLoader):
    param: str
    async def batch_load_fn(self, keys):
        return keys

class Student(BaseModel):
    __pydantic_resolve_expose__ = {'name': 'student_name'}
    name: str = ''
    resolve_hello: str = ''

    def resolve_name(self, context, ancestor_context, loader=LoaderDepend(loader_fn)):
        return '.'

    def post_name(self, loader=LoaderDepend(loader_fn)):
        return '.'

    zones: List[Optional[Zone]] = [None]
    zones2: List[Zone] = []
    zone: Optional[Optional[Zone]] = None

    zeta: Optional[Zeta] = None

    def resolve_zeta(self):
        return dict(name='z')

class Zone(BaseModel):
    name: str
    qs: List[Queue]
    def resolve_qs(self, qs_loader=LoaderDepend(MyLoader)):
        return qs_loader.load(self.name)

class Queue(BaseModel):
    name: str

class Zeta(BaseModel):
    name: str


loader_params = {
    MyLoader: {
        'param': 'aaa'
    }
}
global_loader_param = {
    'param': 'aaa'
}

@pytest.mark.asyncio
async def test_instance_1():
    meta = scan_and_store_metadata(Student)
    loader_instance = _validate_and_create_instance(loader_params, {}, {}, meta)

    assert isinstance(loader_instance['test_field_validate_and_create_loader_instance.loader_fn'] , DataLoader)
    assert isinstance(loader_instance['test_field_validate_and_create_loader_instance.MyLoader'] , MyLoader)

@pytest.mark.asyncio
async def test_instance_2():
    """ test cache works """
    meta = scan_and_store_metadata(Student)
    loader_instance = _validate_and_create_instance(loader_params, {}, {}, meta)

    assert len(loader_instance) == 2

@pytest.mark.asyncio
async def test_instance_3():
    """test global param"""
    meta = scan_and_store_metadata(Student)
    loader_instance = _validate_and_create_instance({}, global_loader_param, {}, meta)

    assert isinstance(loader_instance['test_field_validate_and_create_loader_instance.loader_fn'] , DataLoader)
    assert len(loader_instance) == 2

@pytest.mark.asyncio
async def test_instance_4():
    """raise missing param error"""
    meta = scan_and_store_metadata(Student)

    with pytest.raises(LoaderFieldNotProvidedError):
        loader_instance = _validate_and_create_instance({}, {}, {}, meta)