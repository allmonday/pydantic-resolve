from __future__ import annotations
import pytest
from typing import Optional, List
from pydantic import BaseModel
from aiodataloader import DataLoader
from pydantic_resolve.analysis import Analytic
from pydantic_resolve import Loader, LoaderFieldNotProvidedError
from pydantic_resolve.loader_manager import validate_and_create_loader_instance

async def loader_fn(keys):
    return keys

class MyLoader(DataLoader):
    param: str
    async def batch_load_fn(self, keys):
        return keys

class NoParamLoader(DataLoader):
    """Loader without required parameters"""
    async def batch_load_fn(self, keys):
        return keys

class LoaderWithDefault(DataLoader):
    """Loader with default parameter values"""
    param: str = 'default_value'
    optional_param: str = 'optional_default'

    async def batch_load_fn(self, keys):
        return keys

class Student(BaseModel):
    __pydantic_resolve_expose__ = {'name': 'student_name'}
    name: str = ''
    resolve_hello: str = ''

    def resolve_name(self, context, ancestor_context, loader=Loader(loader_fn)):
        return '.'

    def post_name(self, loader=Loader(loader_fn)):
        return '.'

    zones: List[Optional[Zone]] = [None]
    zones2: List[Zone] = []
    zone: Optional[Optional[Zone]] = None

    zeta: Optional[Zeta] = None

    def resolve_zeta(self):
        return dict(name='z')

    no_param: str = ''
    # For testing NoParamLoader (no required params)
    def resolve_no_param(self, loader=Loader(NoParamLoader)):
        return loader.load(self.name)

    with_default: str = ''
    # For testing LoaderWithDefault (has default values)
    def resolve_with_default(self, loader=Loader(LoaderWithDefault)):
        return loader.load(self.name)

class Zone(BaseModel):
    name: str
    qs: List[Queue]
    def resolve_qs(self, qs_loader=Loader(MyLoader)):
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
    metadata = Analytic().scan(Student)
    loader_instance = validate_and_create_loader_instance(loader_params, {}, {}, metadata)

    assert isinstance(loader_instance['test_field_validate_and_create_loader_instance.loader_fn'] , DataLoader)
    assert isinstance(loader_instance['test_field_validate_and_create_loader_instance.MyLoader'] , MyLoader)

@pytest.mark.asyncio
async def test_instance_2():
    """ test cache works """
    metadata = Analytic().scan(Student)
    loader_instance = validate_and_create_loader_instance(loader_params, {}, {}, metadata)

    # Now there are 4 loaders: loader_fn, MyLoader, NoParamLoader, LoaderWithDefault
    assert len(loader_instance) == 4

@pytest.mark.asyncio
async def test_instance_3():
    """test global param"""
    metadata = Analytic().scan(Student)
    loader_instance = validate_and_create_loader_instance({}, global_loader_param, {}, metadata)

    assert isinstance(loader_instance['test_field_validate_and_create_loader_instance.loader_fn'] , DataLoader)
    assert len(loader_instance) == 4

@pytest.mark.asyncio
async def test_instance_4():
    """raise missing param error"""
    metadata = Analytic().scan(Student)

    with pytest.raises(LoaderFieldNotProvidedError):
        validate_and_create_loader_instance({}, {}, {}, metadata)


@pytest.mark.asyncio
async def test_instance_5():
    """test pre-created loader instances are used directly"""
    metadata = Analytic().scan(Student)

    # Pre-create loader instance - DataLoader doesn't accept param, set after instantiation
    pre_created_loader = MyLoader()
    pre_created_loader.param = 'pre_created'

    pre_created_instances = {
        MyLoader: pre_created_loader
    }

    loader_instance = validate_and_create_loader_instance({}, {}, pre_created_instances, metadata)

    # Verify pre-created instance is used directly
    assert loader_instance['test_field_validate_and_create_loader_instance.MyLoader'].param == 'pre_created'


@pytest.mark.asyncio
async def test_instance_6():
    """test _query_meta is generated correctly"""
    metadata = Analytic().scan(Student)

    loader_instance = validate_and_create_loader_instance(loader_params, {}, {}, metadata)

    # Verify _query_meta contains expected fields
    for path, instance in loader_instance.items():
        if hasattr(instance, '_query_meta'):
            assert 'fields' in instance._query_meta
            assert 'request_types' in instance._query_meta
            assert isinstance(instance._query_meta['fields'], list)
            assert isinstance(instance._query_meta['request_types'], list)


@pytest.mark.asyncio
async def test_instance_7():
    """test loader with default parameter values - no param needed"""
    metadata = Analytic().scan(Student)

    # Need to provide MyLoader params (since Student uses it), but not for LoaderWithDefault
    params_for_others = {
        MyLoader: {'param': 'aaa'}
    }

    # Don't provide LoaderWithDefault params, should use defaults
    loader_instance = validate_and_create_loader_instance(params_for_others, {}, {}, metadata)

    # Verify LoaderWithDefault uses default values
    loader_with_default = loader_instance.get('test_field_validate_and_create_loader_instance.LoaderWithDefault')
    assert loader_with_default is not None
    assert loader_with_default.param == 'default_value'
    assert loader_with_default.optional_param == 'optional_default'


@pytest.mark.asyncio
async def test_instance_8():
    """test loader with default parameter values - override with loader_params"""
    metadata = Analytic().scan(Student)

    # Need to provide MyLoader params, and override LoaderWithDefault defaults
    params_for_others = {
        MyLoader: {'param': 'aaa'}
    }
    custom_params = {
        LoaderWithDefault: {
            'param': 'custom_value',
            'optional_param': 'custom_optional'
        }
    }

    all_params = {**params_for_others, **custom_params}
    loader_instance = validate_and_create_loader_instance(all_params, {}, {}, metadata)

    # Verify custom params take effect
    loader_with_default = loader_instance.get('test_field_validate_and_create_loader_instance.LoaderWithDefault')
    assert loader_with_default is not None
    assert loader_with_default.param == 'custom_value'
    assert loader_with_default.optional_param == 'custom_optional'