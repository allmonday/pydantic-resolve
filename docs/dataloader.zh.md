# 数据加载器 （DataLoader）

DataLoader 是 pydantic-resolve 中非常重要的一个组件， 使用了一个第三方独立库 [aiodataloader](https://github.com/syrusakbary/aiodataloader)， 它常常被作为依赖用在 GraphQL 相关的库中。

它可以解决 GraphQL 的 N+1 查询问题， 能将多个并发查询合并之后变成一次 batch 查询来优化性能。

pydantic-resolve 的内部机制和 GraphQL 有点类似， 所以可以直接使用它来负责数据加载。 对于一些简单的 DataLoader 也可以实现与其他 python GraphQL 框架间的复用。

比如下面代码中, `get_cars_by_child` 会触发多次, 引起 N+1 查询问题. 我们就能通过 DataLoader 来解决.

```python
class Child(BaseModel):
    id: int
    name: str

    cars: List[Car] = []
    # async def resolve_cars(self):
    #     return await get_cars_by_child(self.id) # 产生 N+1 查询

    def resolve_cars(self, loader=LoaderDepend(CarLoader)):
        return loader.load(self.id)

    description: str = ''
    def post_description(self):
        desc = ', '.join([c.name for c in self.cars])
        return f'{self.name} owns {len(self.cars)} cars, they are: {desc}'

children = await Resolver.resolve([
        Child(id=1, name="Titan"), Child(id=1, name="Siri")])
```
## DataLoader 的创建

DataLoader 对象有两种创建方法， 一种是继承 Dataloader：

```python
from aiodataloader import DataLoader

class UserLoader(DataLoader):
    max_batch_size = 20
    async def batch_load_fn(self, keys):
        return await my_batch_get_users(keys)

user_loader = UserLoader()
```

继承的写法可以设置一些 `aiodataloader` 相关的参数， 比如使用 `max_batch_size = 20` 来对 keys 做切片并发。

这几个 param 作为 aiodataloader 的保留参数名， 在新增 param 时需要注意不要重名  (新增 param 的原因会在后面解释)。

另一种则是直接创建一个 `async def batch_load_fn(keys)` 方法， 在 pydantic-resolve 内部会使用 `DataLoader(batch_load_fn)` 来创建实例。

个人更加建议使用第一种写法， 可以在后续获得更大的灵活性。

接下来将介绍 pydantic-resolve 基于 DataLoader 所提供的一些额外功能。


## 提供参数和克隆

DataLoader 可以添加参数， 但需要注意避免和 `aiodataloader` 中的默认参数冲突

- `batch`
- `max_batch_size`
- `cache`
- `cache_key_fn`
- `cache_map`.

比如给 OfficeLoader 添加 `status` 参数， 用来过滤 `open` 的 office。

```python
class OfficeLoader(DataLoader)
    status: Literal['open', 'closed', 'inactive']
    # status: Literal['open', 'closed', 'inactive'] = 'open'

    async def batch_load_fn(self, company_ids):
        offices = await get_offices_by_company_ids_by_status(company_ids, self.status)
        return build_list(offices, company_ids, lambda x: x['company_id'])
```


定义好的参数可以在 Resolver 中通过 loader_params 来设置。

> 注意， param 支持提供默认值， 这样如果使用默认值，就不需要在 Resolver 中设置了。

```python
companies = [
    Company(id=1, name='Aston'),
    Compay(id=2, name="Nicc"),
    Company(id=3, name="Carxx")
]
companies = await Resolver(
    loader_params={
        OfficeLoader: {
            'status': 'open'
        }
    }
).resolve(companies)
```

这里还存在一个可能的问题， 如果同时有两个字段，需要获取不同的 status 的数据呢？ 比如一个需要 open， 另一个需要 close

```python
class Company(BaseModel):
    id: int
    name: str

    open_offices: List[Office] = []
    def resolve_open_offices(self, loader=LoaderDepend(OfficeLoader)):
        return loader.load(self.id)

    closed_offices: List[Office] = []
    def resolve_closed_offices(self, loader=LoaderDepend(OfficeLoader)):
        return loader.load(self.id)
```

两个不同条件的数据没法使用单个 OfficeLoader 来提供数据， 因此 pydantic-resolve 提供了一个工具来克隆两个 OfficeLoader 出来。

```python
from pydantic_resolve import copy_dataloader_kls

OfficeLoader1 = copy_dataloader_kls('OfficeLoader1', OfficeLoader)
OfficeLoader2 = copy_dataloader_kls('OfficeLoader2', OfficeLoader)

class Company(BaseModel):
    id: int
    name: str

    open_offices: List[Office] = []
    def resolve_open_offices(self, loader=LoaderDepend(OfficeLoader1)):
        return loader.load(self.id)

    closed_offices: List[Office] = []
    def resolve_closed_offices(self, loader=LoaderDepend(OfficeLoader2)):
        return loader.load(self.id)

companies = [
    Company(id=1, name='Aston'),
    Company(id=2, name="Nicc"),
    Company(id=3, name="Carxx")
]
companies = await Resolver(
    loader_params={
        OfficeLoader1: {
            'status': 'open'
        }，
        OfficeLoader2: {
            'status': 'closed'
        }
    }
).resolve(companies)
```

## 处理 DataLoader 返回值

如果需要对 `loader.load(self.id)` 的返回值做处理， 可以将 resolve_offices 改为 async，然后使用 await 来获取 loader 的返回值， 就能对数据做处理了。

```python
class Company(BaseModel):
    id: int
    name: str

    offices: List[Office] = []
    async def resolve_offices(self, loader=LoaderDepend(OfficeLoader)):
        offices = await loader.load(self.id)
        return [of for of in offices if of['status'] == 'open']
```

## 申明多个 dataloader

Pydantic resolve 并不限制 loader 的名字， 或者数量， 所以以下的用法也是允许的 ：）

```python
class Company(BaseModel):
    id: int
    name: str

    offices: List[Office] = []
    async def resolve_offices(
            self,
            office_loader=LoaderDepend(OfficeLoader),
            manager_loader=LoaderDepend(ManagerLoader)):
        offices = await office_loader.load(self.id)
        managers = await manager_loader.load(self.id)

        offices = [of for of in offices if of['manager'] in managers]
        return offices
```


## 预先生成 DataLoader 实例

可以提前生成 DataLoader 的实例， 将数据提前设置进去， 这样就能利用 DataLoader 的 cache 机制避免 resolve() 阶段运行时查询的开销。

在一些特定场景会有帮助。

```python
loader = SomeLoader()
loader.prime('tangkikodo', ['tom', 'jerry'])
loader.prime('john', ['mike', 'wallace'])
data = await Resolver(loader_instances={SomeLoader: loader}).resolve(data)
```

## 获取所需的字段信息

DataLoader 中提供了一个隐藏的参数 `self._query_meta`， 它提供了所需的返回字段信息， 借助它就能构建出更加高效的查询。

具体查看 API [定义](./api.md#self_query_meta)


## 查看 DataLoader 实例数据

如果想知道 DataLoader 初始化了哪些实例, 获取了哪些数据, 可以打印出来查看.

```python
resolver = Resolver()
data = await resolver.resolve(data)
print(resolver.loader_instance_cache)
```
