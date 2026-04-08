# ERD 和 AutoLoad

[English](./erd_and_autoload.md)

手动的 `resolve_*` 方法是正确的入口点。但是一旦相同的关系开始在多个响应模型中重复，问题就改变了。

你不再问"我如何加载这个字段？"你在问"这种关系的单一事实来源应该在哪里？"

这就是 ERD 模式变得值得前期成本的点。

## 重复信号

如果你的代码库开始累积这样的模式，关系可能准备好移动到 ERD 中：

- `TaskCard.resolve_owner`
- `TaskDetail.resolve_owner`
- `SprintBoard.resolve_tasks`
- `SprintReport.resolve_tasks`

loader 逻辑可能仍然正确，但关系知识现在重复了。

## 成本 vs 收益

| 问题 | 手动核心 API | ERD + `AutoLoad` |
|---|---|---|
| 第一个接口 | 更快 | 更慢 |
| 前期设置 | 低 | 中 |
| 在许多模型中复用相同关系 | 重复 | 集中 |
| 后续修改关系 | 更新许多 `resolve_*` 方法 | 更新一个声明 |
| GraphQL 和 MCP 复用 | 单独工作 | 自然扩展 |

## ERD 模式中的相同场景

```python
from typing import Annotated, Optional

from pydantic import BaseModel
from pydantic_resolve import (
    Loader,
    Resolver,
    Relationship,
    base_entity,
    build_list,
    build_object,
    config_global_resolver,
)


# --- 伪数据库 ---
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


# --- 实体定义 ---
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


class SprintEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='id', name='tasks', target=list[TaskEntity], loader=task_loader)
    ]
    id: int
    name: str


diagram = BaseEntity.get_diagram()
AutoLoad = diagram.create_auto_load()
config_global_resolver(diagram)


# --- 响应模型（不需要 resolve_* 方法）---
class TaskView(TaskEntity):
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None


class SprintView(SprintEntity):
    tasks: Annotated[list[TaskView], AutoLoad()] = []
    task_count: int = 0

    def post_task_count(self):
        return len(self.tasks)


# --- 解析 ---
raw_sprints = [{"id": 1, "name": "Sprint 24"}]
sprints = [SprintView.model_validate(s) for s in raw_sprints]
sprints = await Resolver().resolve(sprints)

print(sprints[0].model_dump())
# {'id': 1, 'name': 'Sprint 24',
#  'tasks': [
#      {'id': 10, 'title': 'Design docs', 'owner_id': 7,
#       'owner': {'id': 7, 'name': 'Ada'}},
#      {'id': 11, 'title': 'Refine examples', 'owner_id': 8,
#       'owner': {'id': 8, 'name': 'Bob'}},
#  ],
#  'task_count': 2}
```

## 变化了什么

- `resolve_owner` 从视图模型中消失了。
- `resolve_tasks` 从视图模型中消失了。
- 关系声明移动到 `__relationships__` 中。
- `post_task_count` 保持在它应该的地方。

最后一点很重要：ERD 消除了重复的关系连接，但它不替代业务特定的后处理。

## 声明 ERD 的两种方式

### 风格 1：实体类上的内联 `__relationships__`

```python
BaseEntity = base_entity()

class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='owner_id', name='owner', target=UserEntity, loader=user_loader)
    ]
    id: int
    title: str
    owner_id: int

diagram = BaseEntity.get_diagram()
```

当实体类已由当前应用层拥有，并且你乐于直接将关系元数据附加到它时，这种风格效果很好。

### 风格 2：外部 `ErDiagram(...)` 声明

```python
from pydantic_resolve import Entity, ErDiagram

class UserEntity(BaseModel):
    id: int
    name: str

class TaskEntity(BaseModel):
    id: int
    title: str
    owner_id: int

class SprintEntity(BaseModel):
    id: int
    name: str

diagram = ErDiagram(
    entities=[
        Entity(kls=TaskEntity, relationships=[
            Relationship(fk='owner_id', name='owner', target=UserEntity, loader=user_loader)
        ]),
        Entity(kls=SprintEntity, relationships=[
            Relationship(fk='id', name='tasks', target=list[TaskEntity], loader=task_loader)
        ]),
        Entity(kls=UserEntity, relationships=[]),
    ],
)
```

### 何时外部声明更合适

外部 `ErDiagram(...)` 声明通常是更好的选择，当：

- 你不想修改实体类本身
- 同样的实体类在多个模块或服务之间共享
- 你想要一个集中的地方来检查所有关系定义
- 源类来自另一个包或兼容层

简而言之：

- 当关系元数据自然属于实体类型时，使用 `__relationships__`
- 当关系元数据应该与类型定义分离时，使用外部 `ErDiagram(...)`

## AutoLoad 如何工作

`AutoLoad` 并不是魔法。它是一个注释，解析器识别并在分析时将其转换为 `resolve_*` 方法。

```python
AutoLoad = diagram.create_auto_load()

class TaskView(TaskEntity):
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
```

当解析器扫描这个类时，它：

1. 在 `owner` 字段上找到 `AutoLoad()` 注释。
2. 从图中查找具有 `name='owner'` 的 `Relationship`。
3. 生成一个等效的 `resolve_owner` 方法，该方法使用 FK 值调用 loader。

`AutoLoad(origin='tasks')` 参数允许你在字段名称不匹配时指定不同的关系名称：

```python
class SprintView(SprintEntity):
    items: Annotated[list[TaskView], AutoLoad(origin='tasks')] = []
```

## diagram 和 AutoLoad 必须匹配

这个设置不仅仅是仪式：

```python
diagram = BaseEntity.get_diagram()
AutoLoad = diagram.create_auto_load()
config_global_resolver(diagram)
```

`create_auto_load()` 将图特定的关系元数据嵌入到注释中，因此解析器必须配置相同的 `diagram`。

如果你使用自定义解析器而不是全局解析器：

```python
from pydantic_resolve import config_resolver

MyResolver = config_resolver('MyResolver', er_diagram=diagram)
result = await MyResolver().resolve(data)
```

## 关系类型

### 一对一（build_object）

```python
Relationship(
    fk='owner_id',           # 此实体上的 FK 字段
    name='owner',            # 唯一关系名称
    target=UserEntity,       # 单个目标实体
    loader=user_loader       # 每个键返回一个项
)
```

### 一对多（build_list）

```python
Relationship(
    fk='id',                 # 此实体上的 PK 字段
    name='tasks',            # 唯一关系名称
    target=list[TaskEntity], # 列表目标
    loader=task_loader       # 每个键返回一个项列表
)
```

### 处理 None FK 值

```python
Relationship(
    fk='owner_id',
    name='owner',
    target=UserEntity,
    loader=user_loader,
    fk_none_default=None              # 当 FK 为 None 时返回 None
)

# 或使用工厂：
Relationship(
    fk='owner_id',
    name='owner',
    target=UserEntity,
    loader=user_loader,
    fk_none_default_factory=lambda: AnonymousUser()
)
```

### 来自相同 FK 的多个关系

```python
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='owner_id', name='author', target=UserEntity, loader=user_loader),
        Relationship(fk='owner_id', name='reviewer', target=UserEntity, loader=reviewer_loader),
    ]
    id: int
    owner_id: int
```

### 使用 fk_fn 的自定义 FK 转换

当 FK 值需要在传递给 loader 之前转换时：

```python
Relationship(
    fk='tag_ids',             # 逗号分隔的字符串 "1,2,3"
    name='tags',
    target=list[TagEntity],
    loader=tag_loader,
    load_many=True,           # 使用 load_many 而不是 load
    load_many_fn=lambda ids: ids.split(',') if ids else []
)
```

## 从手动 resolve_* 迁移到 ERD

迁移路径是增量式的：

1. 定义镜像你现有响应模型的实体。
2. 添加 `__relationships__` 或外部 `ErDiagram` 声明。
3. 创建 `AutoLoad` 和 `config_global_resolver`。
4. 用 `AutoLoad()` 注释替换 `resolve_*` 方法。
5. 保持 `post_*` 方法不变。

你可以在同一项目中混合手动和 ERD 驱动的解析：

```python
class TaskView(TaskEntity):
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None  # ERD 驱动
    comments: list[CommentView] = []                            # 仍然手动

    def resolve_comments(self, loader=Loader(comment_loader)):  # 手动
        return loader.load(self.id)
```

## 处理循环导入

当实体通过 `target` 相互引用时，你可能会遇到循环导入问题。

### 同模块字符串引用

```python
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        # 字符串 'UserEntity' 在同一模块内解析
        Relationship(fk='owner_id', name='owner', target='UserEntity', loader=user_loader)
    ]
```

### 跨模块引用

```python
# 在 app/models/task.py
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(
            fk='owner_id',
            target='app.models.user:UserEntity',  # module.path:ClassName
            name='owner',
            loader=user_loader
        )
    ]
```

`_resolve_ref` 函数支持：

- 简单类名：`'UserEntity'`（在当前模块中查找）
- 模块路径语法：`'app.models.user:UserEntity'`
- 列表泛型：`list['UserEntity']` 或 `list['app.models.user:UserEntity']`

## 何时还不使用 ERD

在以下情况下继续使用手动核心 API：

- 你只有几个响应模型
- 关系结构仍在快速移动
- 重复成本还不是真实的

ERD 很有价值，但它是扩展步骤，而不是成年礼。

## 下一步

继续阅读 [DataLoader 深入探讨](./dataloader_deep_dive.md) 以了解批处理在底层的工作原理，或跳转到 [ERD 与 DefineSubset](./erd_define_subset.md) 以了解如何从响应中隐藏内部 FK 字段。
