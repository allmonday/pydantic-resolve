# Resolver API

[English](./api_resolver.md)

## Resolver

pydantic-resolve 的主入口。它会遍历 Pydantic 模型树，执行 `resolve_*` 和 `post_*` 方法，并管理 DataLoader 的批量加载。

```python
from pydantic_resolve import Resolver

class Resolver:
    def __init__(
        self,
        loader_params: dict[Any, dict[str, Any]] | None = None,
        global_loader_param: dict[str, Any] | None = None,
        loader_instances: dict[Any, Any] | None = None,
        context: dict[str, Any] | None = None,
        ensure_type: bool = False,
        debug: bool = False,
        enable_from_attribute_in_type_adapter: bool = False,
        annotation: type[T] | None = None,
        split_loader_by_type: bool = False,
    )
```

### 参数

| 参数 | 类型 | 默认值 | 描述 |
|-----------|------|---------|-------------|
| `loader_params` | `dict \| None` | `None` | 按 loader 类键入的各个 loader 配置 |
| `global_loader_param` | `dict \| None` | `None` | 应用于所有 loader 的参数 |
| `loader_instances` | `dict \| None` | `None` | 预创建的 DataLoader 实例 |
| `context` | `dict \| None` | `None` | 可在所有方法中访问的全局上下文字典 |
| `ensure_type` | `bool` | `False` | 验证返回值是否匹配字段类型注解 |
| `debug` | `bool` | `False` | 打印每个节点的计时信息 |
| `enable_from_attribute_in_type_adapter` | `bool` | `False` | 启用 Pydantic v2 的 `from_attributes` 模式 |
| `annotation` | `type \| None` | `None` | 当输入是 Union 类型列表时的显式根类型 |
| `split_loader_by_type` | `bool` | `False` | 按 `request_type` 创建独立的 DataLoader 实例。**与 `loader_instances` 不兼容**。 |

#### split_loader_by_type

当同一棵 resolve 树中有多个字段共享同一个 `DataLoader`，但声明了不同的响应类型（例如 `TaskCard` 只需 2 个字段，`TaskDetail` 需要 20 个字段）时，默认行为是创建一个共享的 loader 实例，其 `_query_meta.fields` 取所有字段**并集**。这意味着轻量视图也会查询全部 20 列。

开启 `split_loader_by_type=True` 后，会为每个 `request_type` 创建独立的 `DataLoader` 实例，各自 `_query_meta` 只包含对应类型实际需要的列。

```python
class Dashboard(BaseModel):
    id: int
    cards: List[TaskCard] = []       # 只需要 id, title
    details: List[TaskDetail] = []   # 需要 id, title, desc, status, ...

    def resolve_cards(self, loader=Loader(TaskLoader)):
        return loader.load(self.id)

    def resolve_details(self, loader=Loader(TaskLoader)):
        return loader.load(self.id)

# 默认：一个 TaskLoader 实例，_query_meta.fields = 所有字段的并集
# 分裂：两个 TaskLoader 实例，各自拥有独立的 _query_meta
result = await Resolver(split_loader_by_type=True).resolve(Dashboard(id=1))
```

**代价：** 分裂后的 loader 实例各自维护独立缓存。如果 `cards` 和 `details` 请求了同一个 key `1`，数据库会被查询两次——分别由各自的 loader 实例触发。

**与 `loader_instances` 不兼容：** 预创建的实例本质上是共享的，无法按类型分裂。同时传入会抛出 `ValueError`。

### resolve()

```python
async def resolve(self, data: T) -> T
```

遍历模型树，执行所有 `resolve_*` 和 `post_*` 方法，并返回完全解析的数据。

### loader_instance_cache

解析完成后，包含所有已创建的 DataLoader 实例：

```python
resolver = Resolver()
result = await resolver.resolve(data)

# 默认模式: dict[str, DataLoader]
#   {'module.TaskLoader': <DataLoader>}
print(resolver.loader_instance_cache['module.TaskLoader'])
```

当 `split_loader_by_type=True` 时，结构为嵌套映射：

```python
# Split 模式: dict[str, dict[tuple[type, ...], DataLoader]]
#   {'module.TaskLoader': {(TaskCard,): inst1, (TaskDetail,): inst2}}
print(resolver.loader_instance_cache['module.TaskLoader'][(TaskCard,)])
```

## config_global_resolver

```python
from pydantic_resolve import config_global_resolver

config_global_resolver(er_diagram: ErDiagram | None = None) -> None
```

将 ERD 全局注入到默认的 `Resolver` 类中。调用此函数后，`Resolver()` 将使用该 ERD 进行 `AutoLoad` 解析。

## config_resolver

```python
from pydantic_resolve import config_resolver

CustomResolver = config_resolver(
    name: str | None = None,
    er_diagram: ErDiagram | None = None,
) -> type[Resolver]
```

创建具有特定 ERD 配置的新 Resolver 类。当需要在同一进程中使用多个 resolver 配置时使用。

```python
BlogResolver = config_resolver('BlogResolver', er_diagram=blog_diagram)
ShopResolver = config_resolver('ShopResolver', er_diagram=shop_diagram)
```

## reset_global_resolver

```python
from pydantic_resolve import reset_global_resolver

reset_global_resolver() -> None
```

将全局 resolver 重置为默认状态（无 ERD）。

## resolve_* 方法

Pydantic 模型中遵循 `resolve_<field_name>` 模式的方法。它们描述如何获取缺失的数据。

```python
class TaskView(BaseModel):
    owner: Optional[UserView] = None

    def resolve_owner(self, loader=Loader(user_loader)):
        return loader.load(self.owner_id)
```

### 支持的参数

| 参数 | 描述 |
|-----------|-------------|
| `loader=Loader(fn)` | DataLoader 依赖 |
| `context` | 来自 `Resolver(context=...)` 的全局上下文 |
| `ancestor_context` | 暴露的祖先值的字典 |
| `parent` | 直接父节点引用 |

方法可以是同步或异步的。返回值会被递归解析。

## post_* 方法

遵循 `post_<field_name>` 模式的方法。它们在后代数据准备就绪后运行。

```python
class SprintView(BaseModel):
    tasks: list[TaskView] = []
    task_count: int = 0

    def post_task_count(self):
        return len(self.tasks)
```

### 支持的参数

| 参数 | 描述 |
|-----------|-------------|
| `context` | 来自 `Resolver(context=...)` 的全局上下文 |
| `ancestor_context` | 暴露的祖先值的字典 |
| `parent` | 直接父节点引用 |
| `loader=Loader(fn)` | DataLoader 依赖（很少需要） |
| `collector=Collector('name')` | 聚合的后代数据 |

返回值**不会**被递归解析。

## post_default_handler

一个在所有其他 `post_*` 方法之后运行的特殊方法。它不会自动赋值——你必须手动设置字段：

```python
class SprintView(BaseModel):
    task_count: int = 0
    summary: str = ""

    def post_task_count(self):
        return len(self.tasks)

    def post_default_handler(self):
        self.summary = f"{self.task_count} tasks"
```
