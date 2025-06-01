import pytest
from typing import List
from pydantic import BaseModel
from aiodataloader import DataLoader
from pydantic_resolve import LoaderDepend, Resolver

class SampleLoader(DataLoader):
    async def batch_load_fn(self, keys):
        """A simple loader that returns the keys as values."""
        return [[dict(id=1, name='me')] for k in keys]

class Student(BaseModel):
    id: int
    name: str

class Student2(BaseModel):
    name: str

class ClassRoom(BaseModel):
    id: int
    name: str

    students: List[Student] = []
    def resolve_students(self, loader=LoaderDepend(SampleLoader)):
        return loader.load(self.id)

    students2: List[Student2] = []
    def resolve_students2(self, loader=LoaderDepend(SampleLoader)):
        return loader.load(self.id)

@pytest.mark.asyncio
async def test_loader_query_meta():
    classrooms = [
        ClassRoom(id=1, name='a'),
        ClassRoom(id=2, name='b'),
    ]
    resolver = Resolver()
    classrooms = await resolver.resolve(classrooms)
    loader_instance = resolver.loader_instance_cache['tests.common.test_loader_query_meta.SampleLoader']

    # _query_meta should be ready after first scan
    assert loader_instance._query_meta['request_types'] == [
        {'name': Student, 'fields': ['id', 'name']},
        {'name': Student2, 'fields': ['name']}
    ]
    assert set(loader_instance._query_meta['fields']) == {'id', 'name'}
