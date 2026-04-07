# ERD and AutoLoad

[English](./erd_and_autoload.md) | [docs](./index.zh.md)

手写 `resolve_*` 是正确的入门方式。但当同一批关系开始在多个响应模型里反复出现时，问题就变了。

此时你不再是在问“这个字段怎么加载”，而是在问“这条关系的唯一事实来源应该放在哪里”。

这正是 ERD 模式开始值得引入的时刻。

## 一个明显的重复信号

如果你的代码里开始不断出现类似这些方法，通常就说明关系定义已经可以收敛进 ERD：

- `TaskCard.resolve_owner`
- `TaskDetail.resolve_owner`
- `SprintBoard.resolve_tasks`
- `SprintReport.resolve_tasks`

Loader 本身也许仍然完全正确，但关系知识已经开始被复制了。

## 成本与收益

| 问题 | 手写 Core API | ERD + `AutoLoad` |
|---|---|---|
| 第一个接口上手速度 | 更快 | 更慢 |
| 前期配置成本 | 低 | 中 |
| 同一关系在多个模型里复用 | 容易重复 | 可以集中管理 |
| 后续修改关系 | 改多个 `resolve_*` | 改一处声明 |
| GraphQL / MCP 复用 | 需要单独处理 | 很自然地延伸 |

## 同一个 Scenario 换成 ERD 模式

```python
from typing import Annotated, Optional

from pydantic import BaseModel
from pydantic_resolve import (
    DefineSubset,
    Relationship,
    base_entity,
    config_global_resolver,
)


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


class TaskView(TaskEntity):
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None


class SprintView(SprintEntity):
    tasks: Annotated[list[TaskView], AutoLoad()] = []
    task_count: int = 0

    def post_task_count(self):
        return len(self.tasks)
```

## 发生了什么变化

- `resolve_owner` 不再写在 view model 上
- `resolve_tasks` 不再写在 view model 上
- 关系声明进入了 `__relationships__`
- `post_task_count` 仍然保留在原来的位置

最后一点尤其重要：ERD 解决的是重复的关系装配，不会替代业务相关的后处理逻辑。

## ERD 有两种声明方式

上面的示例使用的是把关系直接写在实体类上的方式，也就是在类内声明 `__relationships__`：

```python
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='owner_id', name='owner', target=UserEntity, loader=user_loader)
    ]
```

这种写法适合实体类本身就属于当前应用层，并且你也愿意把关系元数据直接挂在类上。

除此之外，还有第二种方式：用 `ErDiagram` 和 `Entity` 在类外部单独声明整张图。

```python
from pydantic import BaseModel
from pydantic_resolve import Entity, ErDiagram, Relationship, config_global_resolver


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
        Entity(
            kls=TaskEntity,
            relationships=[
                Relationship(fk='owner_id', name='owner', target=UserEntity, loader=user_loader)
            ],
        ),
        Entity(
            kls=SprintEntity,
            relationships=[
                Relationship(fk='id', name='tasks', target=list[TaskEntity], loader=task_loader)
            ],
        ),
        Entity(kls=UserEntity, relationships=[]),
    ],
)

AutoLoad = diagram.create_auto_load()
config_global_resolver(diagram)


class TaskView(TaskEntity):
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None


class SprintView(SprintEntity):
    tasks: Annotated[list[TaskView], AutoLoad()] = []
```

### 什么时候更适合用外部 `ErDiagram(...)`

下面这些情况里，外部声明往往更合适：

- 你不希望改动实体类本身
- 同一套实体类会被多个模块或服务共享
- 你希望有一个集中位置查看整张关系图
- 这些类来自别的包，或来自兼容层/桥接层

可以简单理解为：

- 当关系元数据天然属于实体类型本身时，使用 `__relationships__`
- 当关系元数据应该与类型定义分离时，使用外部 `ErDiagram(...)`

## `diagram` 与 `AutoLoad` 必须来自同一份 ERD

下面这组代码不是形式主义：

```python
diagram = BaseEntity.get_diagram()
AutoLoad = diagram.create_auto_load()
config_global_resolver(diagram)
```

`create_auto_load()` 会把特定 diagram 的关系元数据嵌入注解中，所以 resolver 也必须使用同一份 `diagram` 配置。

## 用 `DefineSubset` 隐藏内部字段

如果响应模型不想暴露内部字段，比如 `owner_id`，可以继续建立在同一个 ERD 之上，叠加 `DefineSubset`：

```python
class TaskSummary(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'title'))
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
```

这样既能集中维护关系声明，又能让不同响应暴露不同字段集合。

## 什么时候还不该上 ERD

以下情况继续停留在手写 Core API 更合适：

- 响应模型还不多
- 关系结构还在快速变化
- 重复成本还没有真正出现

ERD 很有价值，但它是规模化步骤，不是入门仪式。

## 下一步

继续读 [GraphQL and MCP](./graphql_and_mcp.zh.md)，看同一份 ERD 如何继续复用到外部接口层。