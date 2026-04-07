# 后处理

[English](./post_processing.md)

`resolve_*` 加载缺失数据。`post_*` 用于当前子树已经组装后应该发生的所有事情。

这种区别很重要。如果读者不能及早理解它，`post_*` 很快就会开始像第二个神秘加载钩子。它不是。

## 扩展相同的 Sprint 示例

既然 `Sprint -> Task -> User` 已经可以被解析，我们可以从完成的子树中导出两个字段：

- `task_count`
- `contributor_names`

```python
import asyncio
from typing import Optional

from pydantic import BaseModel
from pydantic_resolve import Loader, Resolver, build_list, build_object


# --- 伪数据库 ---
USERS = {
    7: {"id": 7, "name": "Ada"},
    8: {"id": 8, "name": "Bob"},
    9: {"id": 9, "name": "Cara"},
}

TASKS = [
    {"id": 10, "title": "Design docs", "sprint_id": 1, "owner_id": 7},
    {"id": 11, "title": "Refine examples", "sprint_id": 1, "owner_id": 8},
    {"id": 12, "title": "Write tests", "sprint_id": 1, "owner_id": 7},
]


async def user_loader(user_ids: list[int]):
    users = [USERS.get(uid) for uid in user_ids]
    return build_object(users, user_ids, lambda u: u.id)


async def task_loader(sprint_ids: list[int]):
    tasks = [t for t in TASKS if t["sprint_id"] in sprint_ids]
    return build_list(tasks, sprint_ids, lambda t: t["sprint_id"])


class UserView(BaseModel):
    id: int
    name: str


class TaskView(BaseModel):
    id: int
    title: str
    owner_id: int
    owner: Optional[UserView] = None

    def resolve_owner(self, loader=Loader(user_loader)):
        return loader.load(self.owner_id)


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


# --- 解析 ---
raw_sprints = [{"id": 1, "name": "Sprint 24"}]
sprints = [SprintView.model_validate(s) for s in raw_sprints]
sprints = await Resolver().resolve(sprints)

print(sprints[0].model_dump())
# {'id': 1, 'name': 'Sprint 24',
#  'tasks': [
#      {'id': 10, 'title': 'Design docs', 'owner_id': 7, 'owner': {'id': 7, 'name': 'Ada'}},
#      {'id': 11, 'title': 'Refine examples', 'owner_id': 8, 'owner': {'id': 8, 'name': 'Bob'}},
#      {'id': 12, 'title': 'Write tests', 'owner_id': 7, 'owner': {'id': 7, 'name': 'Ada'}},
#  ],
#  'task_count': 3,
#  'contributor_names': ['Ada', 'Bob']}
```

## 执行顺序

对于一个 sprint，生命周期如下所示：

```mermaid
flowchart LR
    a["resolve_tasks"] --> b["TaskView.resolve_owner"]
    b --> c["post_task_count"]
    c --> d["post_contributor_names"]
```

确切实现可以在底层是异步的，但心智模型很简单：

1. 首先加载后代（所有 `resolve_*` 方法）。
2. 仅在后代数据准备好后才运行 `post_*`。

那个时机就是为什么 `post_*` 非常适合汇总字段、格式化和业务特定的派生值。

## 经验法则

| 问题 | `resolve_*` | `post_*` |
|---|---|---|
| 需要外部 IO 吗？ | 是 | 通常不需要 |
| 在后代准备好之前运行吗？ | 是 | 否 |
| 适合计数、标签、格式化吗？ | 有时 | 是 |
| 返回值会被再次解析吗？ | 是 | 否 |

## `post_*` 擅长什么

典型用途包括：

- **计数和总计**：`task_count`、`total_price`、`unread_count`
- **排序显示字段**：`contributor_names`、`sorted_tags`
- **去重标签**：`unique_categories`
- **字符串格式化**：`full_title`、`display_name`
- **不应该需要另一个查询的业务汇总**

### 示例：格式化

```python
class TaskView(BaseModel):
    id: int
    title: str
    priority: int
    priority_label: str = ""

    def post_priority_label(self):
        labels = {1: "Low", 2: "Medium", 3: "High"}
        return labels.get(self.priority, "Unknown")
```

### 示例：从嵌套数据丰富

```python
class SprintView(BaseModel):
    id: int
    name: str
    tasks: list[TaskView] = []
    has_overdue: bool = False

    def resolve_tasks(self, loader=Loader(task_loader)):
        return loader.load(self.id)

    def post_has_overdue(self):
        return any(t.due_date < date.today() for t in self.tasks)
```

### 示例：聚合

```python
class OrderView(BaseModel):
    id: int
    items: list[OrderItem] = []
    total: float = 0.0

    def resolve_items(self, loader=Loader(item_loader)):
        return loader.load(self.id)

    def post_total(self):
        return sum(item.price * item.quantity for item in self.items)
```

## `post_*` 不适用于什么

避免将 `post_*` 用作隐藏的关系加载器。如果字段需要外部数据，请将该行为保留在 `resolve_*` 中。

这种分离使代码可读：

- `resolve_*` 回答：**缺失数据从哪里来？**
- `post_*` 回答：**数据准备好后我们用它做什么？**

```python
# 坏：在 post_* 中加载数据
def post_owner(self, loader=Loader(user_loader)):  # 不要这样做
    return loader.load(self.owner_id)

# 好：在 resolve_* 中加载，在 post_* 中转换
def resolve_owner(self, loader=Loader(user_loader)):
    return loader.load(self.owner_id)

def post_owner_display(self):
    return f"{self.owner.name} ({self.owner.email})"
```

## post_* 参数

`post_*` 方法可以接受基本形式之外的其他参数：

### context

访问传递给 `Resolver` 的全局上下文字典：

```python
class SprintView(BaseModel):
    tasks: list[TaskView] = []
    visible_task_count: int = 0

    def resolve_tasks(self, loader=Loader(task_loader)):
        return loader.load(self.id)

    def post_visible_task_count(self, context):
        user_role = context.get('role', 'viewer')
        if user_role == 'admin':
            return len(self.tasks)
        return len([t for t in self.tasks if t.visible])
```

### parent

访问直接父节点。对于树结构很有用：

```python
class TreeNode(BaseModel):
    name: str
    children: list[TreeNode] = []
    depth: int = 0

    def post_depth(self, parent):
        if parent is None:
            return 0
        return parent.depth + 1
```

### ancestor_context

访问通过 `ExposeAs` 暴露的祖先数据（在 [跨层数据流](./cross_layer_data_flow.zh.md) 中介绍）：

```python
class TaskView(BaseModel):
    title: str
    full_title: str = ""

    def post_full_title(self, ancestor_context):
        sprint_name = ancestor_context.get('sprint_name', '')
        return f"{sprint_name} / {self.title}"
```

### collector

通过 `SendTo` 从后代节点收集数据（在 [跨层数据流](./cross_layer_data_flow.zh.md) 中介绍）：

```python
class SprintView(BaseModel):
    tasks: list[TaskView] = []
    contributors: list[UserView] = []

    def resolve_tasks(self, loader=Loader(task_loader)):
        return loader.load(self.id)

    def post_contributors(self, collector=Collector('contributors')):
        return collector.values()
```

## post_default_handler

一个特殊的 post 方法，在所有其他 `post_*` 方法之后运行。它不进行自动赋值 —— 你必须手动设置字段：

```python
class SprintView(BaseModel):
    tasks: list[TaskView] = []
    task_count: int = 0
    summary: str = ""

    def post_task_count(self):
        return len(self.tasks)

    def post_default_handler(self):
        # 在 post_task_count 之后运行
        self.summary = f"{self.task_count} tasks in this sprint"
```

## 有用的边界

`post_*` 可以接受高级参数，如 `context`、`parent`、`ancestor_context` 和 `collector`。但这些功能在基本时机模型已经清楚之后更容易理解。

## 何时停留在此阶段

`resolve_*` + `post_*` 组合涵盖了大部分数据组装需求。大多数接口永远不需要比这更多。

只有当你遇到手动遍历无法干净处理的父子协调时，才继续 [跨层数据流](./cross_layer_data_flow.zh.md)。

## 下一步

继续阅读 [跨层数据流](./cross_layer_data_flow.zh.md)，了解祖先和后代如何在没有显式遍历代码的情况下进行协调。
