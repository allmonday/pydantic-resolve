# 应用场景

介绍 pydantic-resolve 的常用场景， 并且总结一些开发心得。

## 构建数据容器

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

## 构建多层数据

通过继承和扩展的方式， 可将普通 RESTful 的返回数据作为根数据， 然后根据定义自动获取所需的数据和后处理逻辑。

分离根数据(root data)和组合的做法可以分离业务查询逻辑和数据组合逻辑。

比如 Company 数组可能由各种查询方式获得， 比如 id, ids, 或 filter_by 等等， 但却能共享同一种组合。

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



## 跨层级的数据传送： 向子孙节点提供数据

`__pydantic_resolve_expose__` 可以将当前节点中的数据暴露给该节点的所有子孙节点， 这个例子中 Owner 的 name 字段可以被它的子节点 Item 获取。

`{'name': 'owner_name'}` 中， key 是需要暴露的字段名字， value 是全局唯一的别名。

如果有其他中间层节点也使用了 'owner_name', Resolver 会在初始化时检查并报错。

Item 通过 `ancestor_context` 可以通过 `owner_name` 这个全局唯一的别名来获取到 name 的信息。

resolve 和 post 方法都能够读取到 ancestor_context 变量。

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
    def post_description(self, ancestor_context):
        return f'this is item: {self.name}, it belongs to {ancestor_context['owner_name']}'

owners = [
    dict(name="alice", items=[dict(name='car'), dict(name="house")]),
    dict(name="bob", items=[dict(name='shoe'), dict(name="pen")]),
]

owners = await Resolver.resolve([Owner(**o) for o in owners])
```

## 跨层级的数据传送： 向祖先节点发送数据

为了满足跨层级的数据收集需求，可以通过指定 collector 和指定被收集对象的方式， 来灵活收集所需的数据。

数据收集者定义在在 post 方法中， 因为 resolve 还在数据获取阶段， 信息还不完备， post 则是在所有子孙节点都处理完之后才触发的， 能够满足完整性需要。

```python
related_users: list[BaseUser] = []
def post_related_users(self, collector=Collector(alias='related_users')):
    return collector.values()
```

在子孙节点中， 通过定义 `__pydantic_resolve_collect__` 来提供数据， 其中的 key 说明要发送的字段， value 是目标收集者。

key 支持 tuple 的形式， 将多个字段一起发送， value 也支持 tuple， 允许一批 key 指定的字段发送到多个收集者。



```python
from pydantic_resolve import Loader, Collector

class Task(BaseTask):
    __pydantic_resolve_collect__ = {'user': 'related_users'}  # Propagate user to collector: 'related_users'

    user: Optional[BaseUser] = None
    def resolve_user(self, loader=Loader(UserLoader)):
        return loader.load(self.assignee_id)

class Story(BaseStory):
    tasks: list[Task] = []
    def resolve_tasks(self, loader=Loader(StoryTaskLoader)):
        return loader.load(self.id)

    # ---------- Post-processing ------------
    related_users: list[BaseUser] = []
    def post_related_users(self, collector=Collector(alias='related_users')):
        return collector.values()
```

## 树状数据处理

pydantic-resolve 提供了 parent 参数， 可以通过它获取到父节点。

使用这个参数可以方便实现许多功能， 比如拼接出 tag 的完整路径等等。

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


## 在序列化数据中隐藏不需要的临时变量

灵活结合 pydantic 的 `Field(exclude=True)` 或者 dataclass 的 `field(metadata={'exclude': True})`，可以将接收对象不需要的中间变量隐藏起来， 这些数据会在序列化的结果中被过滤掉。


## 总结

换个视角来看 pydantic-resolve 的开发模式通过结构化的定义， 约束了数据的中间计算过程， 通过 resolve 和 post 划分出了数据获取和后处理两个阶段， 结合 expose 和 collect 两个跨层级数据交互的能力， 为节点之间的数据重构提供了方便的手段。 

exclude 的能力也避免了中间变量被返回， 浪费数据空间。

借助 dataloader 这种封装了具体实现细节的通用手段，不受限于是 SQL， No-SQL 或是 RESTful 接口， 让数据的组合可以遵循 ER 模型的结构来进行 。 使得在业务数据处理的生命周期中， 始终保持 ER 关系的清晰， 这对代码的维护非常重要。

对于 A-> B-> C 这种关系， 却只需要获得  A-> C 的数据时， 我们也能借助数据持久层的具体实现 （比如 orm 的 join） ， 直接构造 A-> C 的 dataloader 来优化查询性能， 避免从 A -> B -> C 这个过程中的性能损失。

另外 dataloader 中只返回 BaseClass 的数据， 可以实现 dataloder 的最大程度复用， 比如一个返回 BaseStory 的 dataloader, 它的查询结果可以提供给任意继承了 BaseStory 的子类来使用。 或者提供给 `@ensure_subset` 的子集类来使用。

总儿言之， pydantic-resolve 提供了充足的灵活性， 以 ER 模型的清晰为原则， 获取计算所需的基础数据， 然后根据具体业务对各个节点做修改和移动， 最终构造出所需的业务数据。 两年来的使用体验，相较传统方法, 这个模式可以节省大量代码和后期维护成本。
