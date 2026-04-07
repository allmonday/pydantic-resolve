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
print(resolver.loader_instance_cache)
```

## config_global_resolver

```python
from pydantic_resolve import config_global_resolver

config_global_resolver(er_diagram: ErDiagram) -> None
```

将 ERD 全局注入到默认的 `Resolver` 类中。调用此函数后，`Resolver()` 将使用该 ERD 进行 `AutoLoad` 解析。

## config_resolver

```python
from pydantic_resolve import config_resolver

CustomResolver = config_resolver(name: str, er_diagram: ErDiagram) -> type[Resolver]
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
