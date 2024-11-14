# 简介

pydantic-resolve 是一个对 pydantic 的轻量级封装库。 核心代码逻辑 `resolver.py` 仅 300 行。

简单来说， 它为 pydantic 对象提供了 resolve ( pre hook ) 和 post ( post hook ) 方法，在对数据做广度优先遍历的时候触发这些方法，实现获取和修改数据的效果。

resolve 方法通常用来获取数据， post 方法则可以在数据获取完毕后做额外处理。

同时借助 dataloader， pydantic-resolve 避免了在层层获取数据时容易发生的 N+1 查询， 优化了性能。

除此以外它还提供了 expose 和 collector 机制为跨层的数据提供和收集提供了便利。

## 安装

```
pip install pydantic-resolve
```

从 pydantic-resolve v1.11.0 开始， 将同时兼容 pydantic v1 和 v2。

## 使用场景

### 简单数据拼接

从多个数据源拼接数据， 同层的请求会做并发处理。

```python
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

### 多层数据加载

使用 dataloader 拼接多层数据， 首先提供根数据， 然后让 pydantic-resolve 拼接其他层级的数据。

```python
class Company(BaseModel):
    id: int
    name: str

    offices: List[Office] = []
    def resolve_offices(self, loader=LoaderDepend(OfficeLoader)):
        return loader.load(self.id)

class Office(BaseModel):
    id: int
    city_id: int
    name: str

    members: List[Member] = []
    def resolve_members(self, loader=LoaderDepend(MemberLoader)):
        return loader.load(self.id)

class Member(BaseModel):
    id: int
    office_id: int
    name: str

companies = [Company(id=1, name='Aston'), Compay(id=2, name="Nicc"), Company(id=3, name="Carxx")]
companies = await Resolver().resolve(companies)
```

### 对获取的数据做处理

可以对任意位置的对象做数据处理， 不用维护遍历的代码。

```python
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

### 树状数据处理

更加优雅地处理自引用类型地数据， 避免手写循环遍历。 比如使用 parent 参数拼接出 tag 的完整路径。

```python
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

接下来我们会用一系列例子来示范如何使用 pydantic-resolve 处理各种构建数据时会碰到的问题。
