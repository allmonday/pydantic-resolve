# ERD 与 DefineSubset

[English](./erd_define_subset.md)

`owner_id` 和 `sprint_id` 等实体字段是内部细节。`DefineSubset` 让你选择特定字段用于 API 响应，同时保持 ERD 关系连接不变。

## 目标

你有一个包含内部 FK 字段的实体：

```python
class TaskEntity(BaseModel, BaseEntity):
    id: int
    title: str
    owner_id: int        # 内部 FK
    sprint_id: int       # 内部 FK
```

你希望 API 响应包含 `owner` 关系，但**不**包含 `owner_id` FK 字段：

```json
[
    {
        "id": 1,
        "name": "Sprint 24",
        "tasks": [
            {"id": 10, "title": "Design docs", "owner": {"id": 7, "name": "Ada"}},
            {"id": 11, "title": "Refine examples", "owner": {"id": 8, "name": "Bob"}}
        ],
        "task_count": 2
    }
]
```

输出中没有 `owner_id`，没有 `sprint_id`。

## Step 1：为每个实体定义 Subset

`DefineSubset` 创建一个仅包含你指定字段的新模型：

```python
from pydantic_resolve import DefineSubset


class UserSummary(DefineSubset):
    __subset__ = (UserEntity, ('id', 'name'))


class TaskSummary(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'title'))  # (1)
    owner: Annotated[Optional[UserSummary], AutoLoad()] = None  # (2)
```

1.  只包含 `id` 和 `title` —— `owner_id` 和 `sprint_id` 被排除在响应之外。
2.  `AutoLoad` 仍然能解析关系，因为 ERD 元数据被保留了，即使 FK 字段不在 subset 中。

这等价于：

```python
class TaskSummary(BaseModel):
    id: int
    title: str
    owner: Optional[UserSummary] = None
```

## Step 2：组合 Sprint 响应

```python
class SprintSummary(DefineSubset):
    __subset__ = (SprintEntity, ('id', 'name'))
    tasks: Annotated[list[TaskSummary], AutoLoad()] = []
    task_count: int = 0

    def post_task_count(self):
        return len(self.tasks)
```

## Step 3：运行解析器

```python
raw_sprints = [
    {"id": 1, "name": "Sprint 24"},
    {"id": 2, "name": "Sprint 25"},
]
sprints = [SprintSummary.model_validate(s) for s in raw_sprints]
sprints = await Resolver().resolve(sprints)

for s in sprints:
    print(s.model_dump())
```

输出：

```python
{'id': 1, 'name': 'Sprint 24',
 'tasks': [
     {'id': 10, 'title': 'Design docs', 'owner': {'id': 7, 'name': 'Ada'}},
     {'id': 11, 'title': 'Refine examples', 'owner': {'id': 8, 'name': 'Bob'}},
 ],
 'task_count': 2}
{'id': 2, 'name': 'Sprint 25',
 'tasks': [
     {'id': 12, 'title': 'Bug fixes', 'owner': {'id': 7, 'name': 'Ada'}},
 ],
 'task_count': 1}
```

输出中没有 `owner_id` 或 `sprint_id`。

## DefineSubset vs 常规继承

| 特性 | `DefineSubset` | 常规继承 |
|---------|---------------|-------------------|
| 字段选择 | 显式列表或排除 | 继承所有字段 |
| FK 字段隐藏 | 自动 | 必须覆盖 |
| ERD 关系访问 | 通过元数据保留 | 必须显式 |

```python
# 常规继承：owner_id 会泄露到响应中
class TaskView(TaskEntity):
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None

# DefineSubset：owner_id 被排除
class TaskSummary(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'title'))
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
```

## SubsetConfig 提供更多控制

对于高级场景，使用 `SubsetConfig` 代替元组：

```python
from pydantic_resolve import SubsetConfig

class TaskDetail(DefineSubset):
    __subset__ = SubsetConfig(
        kls=TaskEntity,
        fields=['id', 'title', 'sprint_id'],
    )
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
    sprint: Annotated[Optional[SprintEntity], AutoLoad()] = None
```

### SubsetConfig 参数

| 参数 | 类型 | 描述 |
|-----------|------|-------------|
| `kls` | `type[BaseModel]` | 源实体类 |
| `fields` | `list[str] \| "all" \| None` | 要包含的字段（与 `omit_fields` 互斥） |
| `omit_fields` | `list[str] \| None` | 要排除的字段（与 `fields` 互斥） |
| `expose_as` | `list[tuple[str, str]] \| None` | `ExposeAs` 的字段和别名对 |
| `send_to` | `list[tuple[str, tuple[str, ...] \| str]] \| None` | `SendTo` 的字段和收集器目标对 |
| `excluded_fields` | `list[str] \| None` | 标记为 `Field(exclude=True)` 的字段 |

### 排除字段

包含除特定字段外的所有字段：

```python
class TaskPublic(DefineSubset):
    __subset__ = SubsetConfig(
        kls=TaskEntity,
        omit_fields=['internal_notes', 'audit_log'],
    )
```

### 使用 expose_as 和 send_to

```python
class TaskWithAnnotations(DefineSubset):
    __subset__ = SubsetConfig(
        kls=TaskEntity,
        fields=['id', 'title', 'name'],
        expose_as=[('name', 'task_name')],
        send_to=[('id', 'task_ids')],
    )
```

等价于：

```python
class TaskWithAnnotations(BaseModel):
    id: Annotated[int, SendTo('task_ids')]
    title: str
    name: Annotated[str, ExposeAs('task_name')]
```

## 下一步

继续阅读 [ORM 集成](./orm_integration.zh.md) 了解如何从 SQLAlchemy、Django 或 Tortoise ORM 自动生成 loader。
