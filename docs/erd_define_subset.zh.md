# ERD 与 DefineSubset

[English](./erd_define_subset.md)

当响应模型应该只暴露实体的部分字段时 — 例如，对外部 API 隐藏 `owner_id` — `DefineSubset` 让你可以选择特定字段，同时保持关系声明集中管理。

## 问题

ERD 实体通常包含不应该出现在 API 响应中的内部字段：

```python
class TaskEntity(BaseModel, BaseEntity):
    id: int
    title: str
    owner_id: int        # 内部 FK，不应泄露到 API
    sprint_id: int       # 内部 FK，不应泄露到 API
    internal_notes: str  # 内部字段
```

你可以从头创建单独的响应模型，但这会重复字段定义并失去 ERD 关系连接。

## 基本用法

`DefineSubset` 创建一个仅包含你指定字段的新模型：

```python
from typing import Annotated, Optional

from pydantic_resolve import DefineSubset

class TaskSummary(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'title'))
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
```

这创建一个等价于以下的类：

```python
class TaskSummary(BaseModel):
    id: int      # 继承自 TaskEntity
    title: str   # 继承自 TaskEntity
    owner: Optional[UserEntity] = None  # 你通过 AutoLoad 添加
```

`owner_id` FK 字段不是响应的一部分，但 `AutoLoad` 仍然知道如何解析关系，因为 ERD 元数据被保留了。

## SubsetConfig 提供更多控制

对于高级情况，使用 `SubsetConfig` 而不是元组：

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

这等价于给字段添加注解：

```python
class TaskWithAnnotations(BaseModel):
    id: Annotated[int, SendTo('task_ids')]
    title: str
    name: Annotated[str, ExposeAs('task_name')]
```

## DefineSubset vs 常规继承

两种方法都创建新模型，但用途不同：

| 特性 | `DefineSubset` | 常规继承 |
|---------|---------------|-------------------|
| 字段选择 | 显式列表或排除 | 继承所有字段 |
| FK 字段隐藏 | 自动 | 必须覆盖 |
| ERD 关系访问 | 通过元数据保留 | 必须显式 |
| 源验证 | 内置 | 无 |

### 常规继承（用于比较）

```python
class TaskView(TaskEntity):
    # TaskEntity 的所有字段都被继承，包括 owner_id
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
```

### DefineSubset（隐藏 FK 字段）

```python
class TaskSummary(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'title'))
    # owner_id 不是响应的一部分
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
```

## 完整示例

```python
from typing import Annotated, Optional

from pydantic import BaseModel
from pydantic_resolve import (
    DefineSubset,
    Relationship,
    base_entity,
    build_list,
    build_object,
    config_global_resolver,
)


USERS = {
    7: {"id": 7, "name": "Ada"},
    8: {"id": 8, "name": "Bob"},
}

TASKS = [
    {"id": 10, "title": "Design docs", "sprint_id": 1, "owner_id": 7},
    {"id": 11, "title": "Refine examples", "sprint_id": 1, "owner_id": 8},
]


async def user_loader(user_ids: list[int]):
    users = [USERS.get(uid) for uid in user_ids]
    return build_object(users, user_ids, lambda u: u.id)


async def task_loader(sprint_ids: list[int]):
    tasks = [t for t in TASKS if t["sprint_id"] in sprint_ids]
    return build_list(tasks, sprint_ids, lambda t: t["sprint_id"])


BaseEntity = base_entity()


class UserEntity(BaseModel, BaseEntity):
    id: int
    name: str


class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='owner_id', name='owner', target=UserEntity, loader=user_loader)
    ]
    id: int
    title: str
    owner_id: int
    sprint_id: int


class SprintEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='id', name='tasks', target=list[TaskEntity], loader=task_loader)
    ]
    id: int
    name: str


diagram = BaseEntity.get_diagram()
AutoLoad = diagram.create_auto_load()
config_global_resolver(diagram)


# --- Subsets 隐藏内部 FK 字段 ---
class UserSummary(DefineSubset):
    __subset__ = (UserEntity, ('id', 'name'))


class TaskSummary(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'title'))
    owner: Annotated[Optional[UserSummary], AutoLoad()] = None


class SprintSummary(DefineSubset):
    __subset__ = (SprintEntity, ('id', 'name'))
    tasks: Annotated[list[TaskSummary], AutoLoad()] = []
    task_count: int = 0

    def post_task_count(self):
        return len(self.tasks)


# --- Resolve ---
raw_sprints = [{"id": 1, "name": "Sprint 24"}]
sprints = [SprintSummary.model_validate(s) for s in raw_sprints]
sprints = await Resolver().resolve(sprints)

print(sprints[0].model_dump())
# {'id': 1, 'name': 'Sprint 24',
#  'tasks': [
#      {'id': 10, 'title': 'Design docs', 'owner': {'id': 7, 'name': 'Ada'}},
#      {'id': 11, 'title': 'Refine examples', 'owner': {'id': 8, 'name': 'Bob'}},
#  ],
#  'task_count': 2}
# 注意：输出中没有 owner_id 或 sprint_id
```

## 下一步

继续阅读 [ORM 集成](./orm_integration.zh.md) 了解如何从 SQLAlchemy、Django 或 Tortoise ORM 自动生成 loader。
