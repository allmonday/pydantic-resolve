# 跨层注解

[English](./api_cross_layer.md)

## ExposeAs

```python
from pydantic_resolve import ExposeAs

ExposeAs(alias: str)
```

将字段的值以给定别名暴露给后代节点。后代可以通过 `ancestor_context` 读取它。

```python
class SprintView(BaseModel):
    name: Annotated[str, ExposeAs('sprint_name')]

class TaskView(BaseModel):
    def post_full_title(self, ancestor_context):
        return f"{ancestor_context['sprint_name']} / {self.title}"
```

别名在解析树中应该是全局唯一的。

## SendTo

```python
from pydantic_resolve import SendTo

SendTo(name: str | tuple[str, ...])
```

将字段的值标记为向上发送到父收集器。接受单个收集器名称或名称元组。

```python
# 单个目标
class TaskView(BaseModel):
    owner: Annotated[Optional[User], SendTo('contributors')] = None

# 多个目标
class TaskView(BaseModel):
    owner: Annotated[Optional[User], SendTo(('contributors', 'all_users'))] = None
```

## Collector

```python
from pydantic_resolve import Collector

Collector(alias: str, flat: bool = False)
```

从标记为 `SendTo` 的后代节点收集值。在 `post_*` 方法中使用。

```python
class SprintView(BaseModel):
    contributors: list[User] = []

    def post_contributors(self, collector=Collector('contributors')):
        return collector.values()
```

| 参数 | 类型 | 默认值 | 描述 |
|-----------|------|---------|-------------|
| `alias` | `str` | 必填 | 必须与 `SendTo` 名称匹配 |
| `flat` | `bool` | `False` | 对列表值使用 `extend` 而不是 `append` |

### flat 参数

- `flat=False`: `collector.values()` → `[UserA, [UserB, UserC]]`
- `flat=True`: `collector.values()` → `[UserA, UserB, UserC]`

## ICollector

```python
from pydantic_resolve import ICollector

class ICollector:
    alias: str

    def add(self, val) -> None: ...
    def values(self) -> Any: ...
```

自定义收集器的基础接口。实现 `add` 和 `values`：

```python
class CounterCollector(ICollector):
    def __init__(self, alias):
        self.alias = alias
        self.counter = 0

    def add(self, val):
        self.counter += len(val) if isinstance(val, list) else 1

    def values(self):
        return self.counter
```
