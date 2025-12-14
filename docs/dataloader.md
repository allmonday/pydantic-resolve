# Data Loader (DataLoader)

DataLoader is a key component in `pydantic-resolve`. It is built on top of the third-party library [aiodataloader](https://github.com/syrusakbary/aiodataloader), which is commonly used as a dependency in GraphQL-related libraries.

It solves the GraphQL N+1 query problem by merging many concurrent lookups into a single batch query, which improves performance.

`pydantic-resolve` works in a way that is similar to GraphQL, so DataLoader fits naturally for data fetching. For simple loaders, you can also reuse them across different Python GraphQL frameworks.

In the example below, `get_cars_by_child` would be called many times and cause the N+1 query problem. We can fix it with DataLoader.

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

## Creating a DataLoader

There are two ways to create a DataLoader object. The first one is to subclass `DataLoader`:

```python
from aiodataloader import DataLoader

class UserLoader(DataLoader):
    max_batch_size = 20
    async def batch_load_fn(self, keys):
        return await my_batch_get_users(keys)

user_loader = UserLoader()
```

With subclassing, you can configure `aiodataloader` options. For example, `max_batch_size = 20` will split keys into chunks and run batches.

These params are reserved by `aiodataloader`, so avoid naming conflicts when adding your own params (the reason for custom params is explained later):

- `batch`
- `max_batch_size`
- `cache`
- `cache_key_fn`
- `cache_map`.

The second way is to define an `async def batch_load_fn(keys)` function. Inside `pydantic-resolve`, it will create an instance via `DataLoader(batch_load_fn)`.

In practice, the first approach (subclassing) is recommended because it gives you more flexibility later.

Next, we will introduce some extra features provided by `pydantic-resolve` on top of DataLoader.

## Passing Params and Cloning

You can add params to a DataLoader, but be careful not to conflict with `aiodataloader` default params:

- `batch`
- `max_batch_size`
- `cache`
- `cache_key_fn`
- `cache_map`.

For example, we add a `status` param to `OfficeLoader` to filter only `open` offices.

```python
class OfficeLoader(DataLoader)
    status: Literal['open', 'closed', 'inactive']
    # status: Literal['open', 'closed', 'inactive'] = 'open'

    async def batch_load_fn(self, company_ids):
        offices = await get_offices_by_company_ids_by_status(company_ids, self.status)
        return build_list(offices, company_ids, lambda x: x['company_id'])
```

You can set these params in `Resolver` via `loader_params`.

> Note: params can have default values. If you use a default, you don't need to pass it in `Resolver`.

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

There is a common issue here: what if you have two fields that need different `status` values? For example, one needs `open`, another needs `closed`.

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

One `OfficeLoader` cannot serve two different filters at the same time. So `pydantic-resolve` provides a helper to clone the loader class.

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

## Handling DataLoader Return Values

If you need to post-process the result of `loader.load(self.id)`, you can make your resolver method `async`, then `await` the result and transform it.

```python
class Company(BaseModel):
    id: int
    name: str

    offices: List[Office] = []
    async def resolve_offices(self, loader=LoaderDepend(OfficeLoader)):
        offices = await loader.load(self.id)
        return [of for of in offices if of['status'] == 'open']
```

## Declaring Multiple Dataloaders

`pydantic-resolve` does not restrict loader argument names or the number of loaders you can use. So this pattern is also valid.

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

## Pre-building DataLoader Instances

You can create a DataLoader instance ahead of time and prefill it with data. This lets you use the DataLoader cache and avoid runtime queries during the `resolve()` phase.

This can be useful in specific scenarios.

```python
loader = SomeLoader()
loader.prime('tangkikodo', ['tom', 'jerry'])
loader.prime('john', ['mike', 'wallace'])
data = await Resolver(loader_instances={SomeLoader: loader}).resolve(data)
```

## Getting Required Field Info

DataLoader provides a hidden field `self._query_meta`, which contains metadata about the fields that are required for the output. You can use it to build a more efficient query.

See the API definition here: [./api.md#self_query_meta](./api.md#self_query_meta)

## Inspecting DataLoader Instances

If you want to know which DataLoader instances were initialized and what data they loaded, you can print it.

```python
resolver = Resolver()
data = await resolver.resolve(data)
print(resolver.loader_instance_cache)
```

