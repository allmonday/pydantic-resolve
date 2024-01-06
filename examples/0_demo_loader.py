import asyncio
from typing import List
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend as LD

async def batch_person_age_loader(names: List[str]):
    print(f'query {",".join(names)}')
    _map = {
        'kikodo': 21,
        'John': 14,
        '老王': 40,
    }
    return [_map.get(n) for n in names]

class Person(BaseModel):
    name: str

    age: int = 0
    def resolve_age(self, loader=LD(batch_person_age_loader)):
        return loader.load(self.name)

    is_adult: bool = False
    def post_is_adult(self):
        return self.age > 18

async def simple():
    people = [Person(name=n) for n in ['kikodo', 'John', '老王']]
    people = await Resolver().resolve(people)
    print(people)
    # query query kikodo,John,老王
    # [Person(name='kikodo', age=21, is_adult=True), Person(name='John', age=14, is_adult=False), Person(name='老王', age=40, is_adult=True)]

asyncio.run(simple())

 