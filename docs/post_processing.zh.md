# Post Processing

[English](./post_processing.md) | [docs](./index.zh.md)

`resolve_*` 负责加载缺失数据，`post_*` 负责在当前子树已经组装完成之后做处理。

这个区分非常重要。如果一开始不讲清楚，`post_*` 很容易被误解成另一种神秘的数据加载钩子。它不是。

## 继续扩展同一个 Sprint 例子

既然 `Sprint -> Task -> User` 已经能被完整解析，现在就可以基于这棵完成的子树，派生两个字段：

- `task_count`
- `contributor_names`

```python
class SprintView(BaseModel):
    id: int
    name: str
    tasks: list[TaskView] = []
    task_count: int = 0
    contributor_names: list[str] = []

    def resolve_tasks(self, loader=Loader(task_loader)):
        return loader.load(self.id)

    def post_task_count(self):
        return len(self.tasks)

    def post_contributor_names(self):
        return sorted({task.owner.name for task in self.tasks if task.owner})
```

## 执行顺序

对单个 sprint 来说，生命周期大致是：

```mermaid
flowchart LR
    a["resolve_tasks"] --> b["TaskView.resolve_owner"]
    b --> c["post_task_count"]
    c --> d["post_contributor_names"]
```

底层可以是异步调度，但心智模型保持简单就够了：

1. 先把后代节点的数据装配好
2. 再执行当前节点上的 `post_*`

正因为时机在后面，`post_*` 非常适合做汇总、格式化和业务派生字段。

## 快速判断表

| 问题 | `resolve_*` | `post_*` |
|---|---|---|
| 需要外部 IO 吗？ | 是 | 通常不需要 |
| 执行时后代节点准备好了吗？ | 没有 | 是 |
| 适合做计数、标签、格式化吗？ | 有时可以 | 非常适合 |
| 返回值还会继续被解析吗？ | 会 | 不会 |

## `post_*` 适合做什么

典型用途包括：

- 计数与汇总
- 排序后的展示字段
- 去重后的标签列表
- 基于已加载后代数据的字符串拼装
- 不值得再单独查询的业务摘要字段

## `post_*` 不适合做什么

不要把 `post_*` 当成隐藏的关联加载器。如果某个字段需要外部数据，就把它留在 `resolve_*` 中。

保持这个分工，代码会非常清楚：

- `resolve_*` 回答：缺的数据从哪里来？
- `post_*` 回答：数据都到位之后要怎么处理？

## 一个实用边界

`post_*` 还可以接收 `context`、`parent`、`ancestor_context`、`collector` 等高级参数。但这些能力只有在读者已经真正理解了执行时机之后，才值得继续讲。

## 下一步

继续读 [Cross-Layer Data Flow](./cross_layer_data_flow.zh.md)，看祖先节点和后代节点如何在不手写树遍历的情况下协作。