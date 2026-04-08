# DataLoader 工具

[English](./api_dataloader.md)

## Loader

```python
from pydantic_resolve import Loader

Loader(loader_fn: Callable)
```

在 `resolve_*` 方法签名中声明 DataLoader 依赖。

```python
def resolve_owner(self, loader=Loader(user_loader)):
    return loader.load(self.owner_id)
```

## build_object

```python
from pydantic_resolve import build_object

build_object(items: list, keys: list, get_key: Callable) -> list[item | None]
```

将获取的项与请求的键顺序对齐。每个键返回一个项（或 `None`）。用于一对一关系。

```python
async def user_loader(user_ids: list[int]):
    users = await fetch_users(user_ids)
    return build_object(users, user_ids, lambda u: u.id)
# 结果: [User7, User8, None, User9]
```

## build_list

```python
from pydantic_resolve import build_list

build_list(items: list, keys: list, get_key: Callable) -> list[list[item]]
```

按键分组获取的项并与请求的键顺序对齐。每个键返回一个项列表。用于一对多关系。

```python
async def task_loader(sprint_ids: list[int]):
    tasks = await fetch_tasks(sprint_ids)
    return build_list(tasks, sprint_ids, lambda t: t.sprint_id)
# 结果: [[Task1, Task2], [Task3], []]
```

## copy_dataloader_kls

```python
from pydantic_resolve import copy_dataloader_kls

copy_dataloader_kls(name: str, origin_kls: type) -> type
```

创建具有新名称的 DataLoader 类的副本。当需要同一个 loader 的多个参数化实例时很有用。

```python
OpenLoader = copy_dataloader_kls('OpenLoader', OfficeLoader)
ClosedLoader = copy_dataloader_kls('ClosedLoader', OfficeLoader)
```

## 空 Loader 生成器

```python
from pydantic_resolve.utils.dataloader import (
    generate_strict_empty_loader,
    generate_list_empty_loader,
    generate_single_empty_loader,
)
```

| 函数 | 缺失键时返回 |
|----------|----------------------|
| `generate_single_empty_loader(name)` | `None` |
| `generate_list_empty_loader(name)` | `[]` |
| `generate_strict_empty_loader(name)` | 抛出错误 |

## DataLoader (aiodataloader)

pydantic-resolve 使用 `aiodataloader.DataLoader` 作为基类。关键配置属性：

| 属性 | 类型 | 默认值 | 描述 |
|-----------|------|---------|-------------|
| `batch` | `bool` | `True` | 启用批量加载 |
| `max_batch_size` | `int \| None` | `None` | 每批最大键数 |
| `cache` | `bool` | `True` | 启用键缓存 |
| `cache_key_fn` | `Callable \| None` | `None` | 自定义缓存键函数 |

### _query_meta

关于响应模型需要哪些字段的只读元数据：

```python
class MyLoader(DataLoader):
    async def batch_load_fn(self, keys):
        fields = self._query_meta.get('fields', ['*'])
        # fields = ['id', 'name']
```

### _context

接收来自 `Resolver(context=...)` 的全局上下文：

```python
class MyLoader(DataLoader):
    _context: dict

    async def batch_load_fn(self, keys):
        user_id = self._context['user_id']
```
