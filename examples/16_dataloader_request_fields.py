import asyncio
from typing import List
from pydantic import BaseModel
from aiodataloader import DataLoader
from pydantic_resolve import LoaderDepend, Resolver

class SampleLoader(DataLoader):
    async def batch_load_fn(self, keys):
        data = {
            1: [{'id': 1, 'name': 'me', 'age': 18}],
            2: [{'id': 2, 'name': 'you', 'age': 20}],
        }
        print(self._query_meta['fields'])
        print(self._query_meta['request_types'])
        return [[{
                    k: v for k, v in d.items() if k in self._query_meta['ields'] 
                 } for d in data.get(key, [])] for key in keys]

class Student(BaseModel):
    id: int
    name: str

class ClassRoom(BaseModel):
    id: int
    name: str

    students: List[Student] = []
    def resolve_students(self, loader=LoaderDepend(SampleLoader)):
        return loader.load(self.id)

async def main():
    classrooms = [
        ClassRoom(id=1, name='a'),
        ClassRoom(id=2, name='b'),
    ]
    resolver = Resolver()
    classrooms = await resolver.resolve(classrooms)
    for cls in classrooms:
        print(cls.dict())


asyncio.run(main())