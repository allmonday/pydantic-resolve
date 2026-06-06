# 后处理

[English](./post_processing.md)

`resolve_*` 加载缺失数据。`post_*` 计算派生字段 —— 依赖已组装子树的值，如计数、汇总和格式化字符串。

## 目标

在核心 API 的 `Sprint -> Task -> User` 树基础上，你现在需要每个 sprint 包含：

- `task_count` —— 该 sprint 的任务数量
- `contributor_names` —— 去重且排序的所有负责人姓名

```json
[
    {
        "id": 1,
        "name": "Sprint 24",
        "tasks": [
            {"id": 10, "title": "Design docs", "owner": {"id": 7, "name": "Ada"}},
            {"id": 11, "title": "Refine examples", "owner": {"id": 8, "name": "Bob"}},
            {"id": 12, "title": "Write tests", "owner": {"id": 7, "name": "Ada"}}
        ],
        "task_count": 3,
        "contributor_names": ["Ada", "Bob"]
    },
    {
        "id": 2,
        "name": "Sprint 25",
        "tasks": [
            {"id": 13, "title": "Bug fixes", "owner": {"id": 7, "name": "Ada"}}
        ],
        "task_count": 1,
        "contributor_names": ["Ada"]
    }
]
```

这些字段不从 loader 获取 —— 它们从每个 sprint 已有的数据中推导。解析器会为列表中的每个 sprint 自动计算这些值。

## Step 1：添加 post_* 方法

在同一个 `SprintView` 上添加 `post_task_count` 和 `post_contributor_names`：

```python
class SprintView(BaseModel):
    id: int
    name: str
    tasks: list[TaskView] = []
    task_count: int = 0  # (1)
    contributor_names: list[str] = []

    def resolve_tasks(self, loader=Loader(task_loader)):
        return loader.load(self.id)

    def post_task_count(self):  # (2)
        return len(self.tasks)

    def post_contributor_names(self):
        return sorted({task.owner.name for task in self.tasks if task.owner})
```

1.  派生字段以默认值开始，就像 `resolve_*` 字段以 `None` 开始一样。
2.  方法名遵循 `post_<field_name>`。返回值会赋给匹配的字段。

## Step 2：运行解析器

同样的 `Resolver().resolve()` 调用处理一切：

```python
raw_sprints = [
    {"id": 1, "name": "Sprint 24"},
    {"id": 2, "name": "Sprint 25"},
]
sprints = [SprintView.model_validate(s) for s in raw_sprints]
sprints = await Resolver().resolve(sprints)

for s in sprints:
    print(s.model_dump())
```

输出：

```python
{'id': 1, 'name': 'Sprint 24',
 'tasks': [
     {'id': 10, 'title': 'Design docs', 'owner_id': 7, 'owner': {'id': 7, 'name': 'Ada'}},
     {'id': 11, 'title': 'Refine examples', 'owner_id': 8, 'owner': {'id': 8, 'name': 'Bob'}},
     {'id': 12, 'title': 'Write tests', 'owner_id': 7, 'owner': {'id': 7, 'name': 'Ada'}},
 ],
 'task_count': 3,
 'contributor_names': ['Ada', 'Bob']}
{'id': 2, 'name': 'Sprint 25',
 'tasks': [
     {'id': 13, 'title': 'Bug fixes', 'owner_id': 7, 'owner': {'id': 7, 'name': 'Ada'}},
 ],
 'task_count': 1,
 'contributor_names': ['Ada']}
```

## 执行顺序

```mermaid
flowchart LR
    a["resolve_tasks"] --> b["TaskView.resolve_owner"]
    b --> c["post_task_count"]
    c --> d["post_contributor_names"]
```

1.  所有 `resolve_*` 方法先运行 —— 递归加载后代数据。
2.  `post_*` 只在后代数据准备好之后运行。

这个时序就是 `post_*` 适合派生字段的原因 —— 计数、汇总以及其他从已解析子树中计算的值。

## resolve_* vs post_*

| | `resolve_*` | `post_*` |
|---|---|---|
| 需要外部 IO 吗？ | 是 | 通常不需要 |
| 在后代准备好之前运行吗？ | 是 | 否 |
| 适合计数、求和、格式化吗？ | 有时 | 是 |
| 返回值会继续被解析吗？ | 会 | 不会 |

## 常见模式

格式化：

```python
class TaskView(BaseModel):
    priority: int
    priority_label: str = ""

    def post_priority_label(self):
        return {1: "Low", 2: "Medium", 3: "High"}.get(self.priority, "Unknown")
```

聚合：

```python
class OrderView(BaseModel):
    items: list[OrderItem] = []
    total: float = 0.0

    def resolve_items(self, loader=Loader(item_loader)):
        return loader.load(self.id)

    def post_total(self):
        return sum(item.price * item.quantity for item in self.items)
```

从嵌套数据丰富：

```python
class SprintView(BaseModel):
    tasks: list[TaskView] = []
    has_overdue: bool = False

    def resolve_tasks(self, loader=Loader(task_loader)):
        return loader.load(self.id)

    def post_has_overdue(self):
        return any(t.due_date < date.today() for t in self.tasks)
```

## post_* 参数

### context

访问传递给 `Resolver` 的全局上下文字典：

```python
def post_visible_task_count(self, context):
    user_role = context.get('role', 'viewer')
    if user_role == 'admin':
        return len(self.tasks)
    return len([t for t in self.tasks if t.visible])
```

### parent

访问直接父节点 —— 适用于树结构：

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

访问通过 `ExposeAs` 暴露的祖先数据（见 [跨层数据流](./cross_layer_data_flow.zh.md)）：

```python
def post_full_title(self, ancestor_context):
    sprint_name = ancestor_context.get('sprint_name', '')
    return f"{sprint_name} / {self.title}"
```

### collector

通过 `SendTo` 从后代节点收集数据（见 [跨层数据流](./cross_layer_data_flow.zh.md)）：

```python
def post_contributors(self, collector=Collector('contributors')):
    return collector.values()
```

### loader

`post_*` 也可以使用 `Loader` —— 与 `resolve_*` 相同的参数。这是一个逃生出口，适用于加载 key 本身来自已解析字段的场景：

```python
def resolve_owner(self, loader=Loader(user_loader)):
    return loader.load(self.owner_id)

def post_department_name(self, loader=Loader(department_loader)):
    # owner.department_id 只有在 resolve_owner 之后才可用
    if self.owner:
        return loader.load(self.owner.department_id)
```

两个注意事项：

1.  `post_*` 中通过 loader 加载的数据**不会递归解析** —— 嵌套的 `resolve_*` / `post_*` 不会执行。
2.  同一对象上的其他 `post_*` 方法无法依赖它。

## post_default_handler

一个特殊方法，在所有其他 `post_*` 方法之后运行。它不自动赋值 —— 你需要手动设置字段：

```python
def post_task_count(self):
    return len(self.tasks)

def post_default_handler(self):
    # 在 post_task_count 之后运行
    self.summary = f"{self.task_count} tasks in this sprint"
```

## 何时停留在此阶段

`resolve_*` + `post_*` 组合涵盖了大部分数据组装需求。大多数接口不需要更多。

## 下一步

- [跨层数据流](./cross_layer_data_flow.zh.md) —— 在父子节点之间共享数据，无需显式遍历代码。
- [ERD 与 AutoLoad](./erd_and_autoload.zh.md) —— 当关系开始在多个模型中重复时，集中管理关系声明。
