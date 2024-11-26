# Use Cases

Some scenarios where pydantic-resolve can be used.

## Simple Data Concatenation

Concatenate data from multiple data sources (requests at the same level will be automatically concurrent).

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

## Multi-layer Data Loading

Use dataloader to concatenate multi-layer data. First, provide the root data, and then let pydantic-resolve concatenate the data of other levels.

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

## Processing Retrieved Data

You can process data at any position of the object without worrying about the traversal logic.

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

## Tree Data Processing

Handle self-referential data types more elegantly.

For example, use the parent parameter to concatenate the full path of the tag.

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
