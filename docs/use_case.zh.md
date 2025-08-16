# 应用场景

一些 pydantic-resolve 可以使用的场景。

## 简单据构建

定义一个容器结构， 然后在里面查询所需的相关数据， 比较适合面向 UI 的数据构建。

同层的数据会自动并发查询。

```python
from pydantic import BaseModel
from pydantic_resolve import Resolver

class BusinessPage(BaseModel):
    data: List[str] = []
    async def resolve_data(self):
        return await get_data()

    records: List[Record] = []
    async def resolve_records(self):
        return await get_records()

retData = BusinessPage()
retData = await Resolver().resolve(retData)
```

## 多层数据构建

通过继承和扩展的方式， 可将普通 RESTful 的返回数据作为根数据， 然后根据定义自动获取所需的数据和后处理逻辑。

根数据的做法可以分离业务查询逻辑和数据组合逻辑

比如 Company 数组可能由各种查询方式获得， 比如 id, ids, 或根据字段来过滤， 但却能共享同一种组合逻辑。

另外， 使用 dataloader 可以自动规避 N+1 查询的问题。

```python
from pydantic import BaseModel
from pydantic_resolve import Resolver, DoaderDepend

class BaseCompany(BaseModel):
    id: int
    name: str

class Baseffice(BaseModel):
    id: int
    company_id: int
    name: str

class BaseMember(BaseModel):
    id: int
    office_id: int
    name: str

# ------- composition ----------
class Company(BaseCompany):
    offices: List[Office] = []
    def resolve_offices(self, loader=LoaderDepend(OfficeLoader)):
        return loader.load(self.id)

class Office(BaseOffice):
    members: List[Member] = []
    def resolve_members(self, loader=LoaderDepend(MemberLoader)):
        return loader.load(self.id)


raw_companies = [
    BaseCompany(id=1, name='Aston'),
    BaseCompany(id=2, name="Nicc"),
    BaseCompany(id=3, name="Carxx")]

companies = [Company.model_validate(c, from_attributes=True) for c in raw_companies]

data = await Resolver().resolve(companies)
```

## 对获取的数据做处理

可以对任意位置的对象做数据处理，不用关心遍历逻辑。

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

## 树状数据处理

更加优雅地处理自引用类型地数据。

比如使用 parent 参数拼接出 tag 的完整路径。

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
