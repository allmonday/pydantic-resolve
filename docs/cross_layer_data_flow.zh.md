# Cross-Layer Data Flow

[English](./cross_layer_data_flow.md) | [docs](./index.zh.md)

大多数用户第一天并不需要这些能力。但当父子节点需要跨多层协作时，`ExposeAs`、`SendTo` 和 `Collector` 可以让这类逻辑继续保持声明式，而不是重新回到手写遍历。

这里仍然坚持使用同一个 `Sprint -> Task -> User` scenario。

## 我们要解决的两个问题

1. 每个 task 都需要一个 `full_title`，例如 `Sprint 24 / Design docs`
2. sprint 需要把所有 task 的 owner 汇总成 `contributors`

这两个问题都跨越了对象边界，这正是跨层数据流开始有价值的时候。

## 完整示例

```python
from typing import Annotated, Optional

from pydantic import BaseModel
from pydantic_resolve import Collector, ExposeAs, Loader, SendTo


class SprintView(BaseModel):
    id: int
    name: Annotated[str, ExposeAs('sprint_name')]
    tasks: list['TaskView'] = []
    contributors: list['UserView'] = []

    def resolve_tasks(self, loader=Loader(task_loader)):
        return loader.load(self.id)

    def post_contributors(self, collector=Collector('contributors')):
        return collector.values()


class TaskView(BaseModel):
    id: int
    title: str
    owner_id: int
    owner: Annotated[Optional['UserView'], SendTo('contributors')] = None
    full_title: str = ""

    def resolve_owner(self, loader=Loader(user_loader)):
        return loader.load(self.owner_id)

    def post_full_title(self, ancestor_context):
        return f"{ancestor_context['sprint_name']} / {self.title}"
```

## 用 `ExposeAs` 向下传递

`ExposeAs('sprint_name')` 的含义是：把 `SprintView.name` 这个字段以 `sprint_name` 的别名暴露给所有后代节点。

所以 `TaskView.post_full_title` 才能读取：

```python
ancestor_context['sprint_name']
```

这种能力适合后代节点需要读取祖先上下文的场景，例如：

- sprint 名称
- 租户 id
- 权限范围
- 展示前缀

### 一个实用规则

Expose 的别名最好在整棵解析树中保持全局唯一。否则不同祖先使用同一个 alias 表示不同含义时，会让行为变得很难推理。

## 用 `SendTo` 和 `Collector` 向上汇总

`SendTo('contributors')` 的意思是：`TaskView.owner` 这个字段会向上发送到名为 `contributors` 的 collector。

而 `SprintView.post_contributors` 则负责消费这些已汇总的数据：

```python
def post_contributors(self, collector=Collector('contributors')):
    return collector.values()
```

这种能力适合父节点需要从后代聚合信息的场景，例如：

- 全部贡献者
- 子树中所有标签
- 多层节点涉及到的全部用户

## 生命周期上的理解方式

即使引入了跨层能力，整体依然遵守同样的两阶段模型：

1. 祖先节点先把数据向下暴露
2. 后代节点继续 resolve 和 post
3. 后代值向上发送
4. 父节点在自己的 `post_*` 中消费 collector

关键点是：你依然不需要自己写树遍历代码。

## 什么时候值得引入这些能力

以下情况适合使用：

- 子节点确实需要祖先上下文，而且显式传参会让代码四处扩散
- 父节点确实需要从多个后代聚合信息，否则 endpoint 层会堆满手写循环

以下情况则更适合保持简单：

- 当前节点本地就能算出字段
- 只涉及一层关系
- 显式写法仍然足够短、足够直观

## 下一步

当你发现 `resolve_*` 关系声明开始在多个模型中重复出现时，继续读 [ERD and AutoLoad](./erd_and_autoload.zh.md)。