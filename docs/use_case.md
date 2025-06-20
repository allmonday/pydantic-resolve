# Use Cases

Practical scenarios demonstrating pydantic-resolve's capabilities in data composition and resolution.

## Simple Data Aggregation

Aggregate data from multiple data sources with automatic concurrency for same-level requests.

```python
from pydantic import BaseModel
from pydantic_resolve import Resolver

class ReturnData(BaseModel):
    data: List[str] = []
    async def resolve_data(self):
        return await get_data()

    records: List[Record] = []
    async def resolve_records(self):
        return await get_records()

retData = ReturnData()
retData = await Resolver().resolve(retData)
```

## Hierarchical Data Composition

Leverage DataLoader to compose multi-layer relational data. Initialize root entities and let pydantic-resolve handle nested relationship resolution.

```python
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend

class Company(BaseModel):
    id: int
    name: str

    offices: List[Office] = []
    def resolve_offices(self, loader=LoaderDepend(OfficeLoader)):
        return loader.load(self.id)

class Office(BaseModel):
    id: int
    company_id: int
    name: str

    members: List[Member] = []
    def resolve_members(self, loader=LoaderDepend(MemberLoader)):
        return loader.load(self.id)

class Member(BaseModel):
    id: int
    office_id: int
    name: str

companies = [
    Company(id=1, name='Aston'),
    Compay(id=2, name="Nicc"),
    Company(id=3, name="Carxx")]
companies = await Resolver().resolve(companies)
```

## Data Transformation and Enhancement

Apply business logic and data transformations at any node in the object graph without manual tree traversal.

```python
from pydantic import BaseModel
from pydantic_resolve import Resolver

class Owner(BaseModel):
    __pydantic_resolve_expose__ = { 'name': 'owner_name' }
    name: str
    items: List[Item]

class Item(BaseModel):
    name: str

    description: str = ''
    def resolve_description(self, ancestor_context):
        return f'this is item: {self.name}, it belongs to {ancestor_context['owner_name']}'

owners = [
    dict(name="alice", items=[dict(name='car'), dict(name="house")]),
    dict(name="bob", items=[dict(name='shoe'), dict(name="pen")]),
]

owners = await Resolver.resolve([Owner.parse_obj(o) for o in owners])
```

## Recursive Data Structure Resolution

Handle self-referential models and recursive data structures with built-in parent context access.

Compute derived fields using parent node information:

```python
from pydantic import BaseModel
from pydantic_resolve import Resolver

class Tag(BaseModel):
    name: str

    full_path: str = ''
    def resolve_full_path(self, parent):
        if parent:
            return f'{parent.full_path}/{self.name}'
        else:
            return self.name

    children: List[Tag] = []


tag_data = dict(name='root', children=[
        dict(name='a', children=[
            dict(name='b', children=[
                dict(name='e', chidrent=[])
            ])
        ])
    ])

tag = Tag.parse_obj(tag_data)
tag = await Resolver().resolve(tag)
```

Tree construction from flat data structures using primed loaders:

```python
from __future__ import annotations
from collections import defaultdict
import asyncio
from typing import List
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend
from pydantic_resolve.utils.dataloader import ListEmptyLoader

roots = [{ 'id': 1, 'content': 'root' }, {'id': 6, 'content': '6'}]
records = [
    {'id': 2, 'parent': 1, 'content': '2'},
    {'id': 3, 'parent': 1, 'content': '3'},
    {'id': 4, 'parent': 2, 'content': '4'},
    {'id': 5, 'parent': 3, 'content': '5'},
    {'id': 7, 'parent': 6, 'content': '7'},
]

class Tree(BaseModel):
    id: int
    content: str

    children: List[Tree] = []
    def resolve_children(self, loader=LoaderDepend(ListEmptyLoader)):
        return loader.load(self.id)

async def main():
    import json
    loader = ListEmptyLoader()

    # prime parent-child mappings for tree construction
    _records = defaultdict(list)
    for r in records:
        _records[r['parent']].append(r)
    for k, v in _records.items():
        loader.prime(k, v)

    trees = [Tree(**r) for r in roots]
    trees = await Resolver(
        loader_instances={ ListEmptyLoader: loader }
    ).resolve(trees)
    trees = [t.dict() for t in trees]
    print(json.dumps(trees, indent=2))
```
