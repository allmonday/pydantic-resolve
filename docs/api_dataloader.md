# DataLoader Utilities

[中文版](./api_dataloader.zh.md)

## Loader

```python
from pydantic_resolve import Loader

Loader(loader_fn: Callable)
```

Declares a DataLoader dependency inside `resolve_*` method signatures.

```python
def resolve_owner(self, loader=Loader(user_loader)):
    return loader.load(self.owner_id)
```

## build_object

```python
from pydantic_resolve import build_object

build_object(items: list, keys: list, get_key: Callable) -> list[item | None]
```

Aligns fetched items with the requested key order. Returns one item (or `None`) per key. For one-to-one relationships.

```python
async def user_loader(user_ids: list[int]):
    users = await fetch_users(user_ids)
    return build_object(users, user_ids, lambda u: u.id)
# Result: [User7, User8, None, User9]
```

## build_list

```python
from pydantic_resolve import build_list

build_list(items: list, keys: list, get_key: Callable) -> list[list[item]]
```

Groups fetched items by key and aligns with the requested key order. Returns a list of items per key. For one-to-many relationships.

```python
async def task_loader(sprint_ids: list[int]):
    tasks = await fetch_tasks(sprint_ids)
    return build_list(tasks, sprint_ids, lambda t: t.sprint_id)
# Result: [[Task1, Task2], [Task3], []]
```

## copy_dataloader_kls

```python
from pydantic_resolve import copy_dataloader_kls

copy_dataloader_kls(name: str, origin_kls: type) -> type
```

Creates a copy of a DataLoader class with a new name. Useful when you need multiple parameterized instances of the same loader.

```python
OpenLoader = copy_dataloader_kls('OpenLoader', OfficeLoader)
ClosedLoader = copy_dataloader_kls('ClosedLoader', OfficeLoader)
```

## Empty Loader Generators

```python
from pydantic_resolve.utils.dataloader import (
    generate_strict_empty_loader,
    generate_list_empty_loader,
    generate_single_empty_loader,
)
```

| Function | Returns on missing key |
|----------|----------------------|
| `generate_single_empty_loader(name)` | `None` |
| `generate_list_empty_loader(name)` | `[]` |
| `generate_strict_empty_loader(name)` | Raises error |

## DataLoader (aiodataloader)

pydantic-resolve uses `aiodataloader.DataLoader` as its base class. Key configuration attributes:

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `batch` | `bool` | `True` | Enable batching |
| `max_batch_size` | `int \| None` | `None` | Max keys per batch |
| `cache` | `bool` | `True` | Enable key caching |
| `cache_key_fn` | `Callable \| None` | `None` | Custom cache key function |

### _query_meta

Read-only metadata about what fields the response model needs:

```python
class MyLoader(DataLoader):
    async def batch_load_fn(self, keys):
        fields = self._query_meta.get('fields', ['*'])
        # fields = ['id', 'name']
```

### _context

Receives the global context from `Resolver(context=...)`:

```python
class MyLoader(DataLoader):
    _context: dict

    async def batch_load_fn(self, keys):
        user_id = self._context['user_id']
```
