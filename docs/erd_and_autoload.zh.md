# ERD 和 AutoLoad

[English](./erd_and_autoload.md)

手写 `resolve_*` 是正确的入口点。但当相同的关系开始在多个响应模型中重复时，问题就变了：你不再问"如何加载这个字段？"而是在问"这种关系的唯一事实来源应该放在哪里？"

ERD 模式将关系声明集中到实体类中。`AutoLoad` 让你完全不需要写 `resolve_*`。

## 重复信号

如果你的代码库开始出现这样的模式，关系就准备好进入 ERD 了：

- `TaskCard.resolve_owner`
- `TaskDetail.resolve_owner`
- `SprintBoard.resolve_tasks`
- `SprintReport.resolve_tasks`

loader 逻辑仍然正确，但关系知识已经重复了。

## 成本 vs 收益

| 问题 | 手写 Core API | ERD + `AutoLoad` |
|---|---|---|
| 第一个接口 | 更快 | 更慢 |
| 前期配置 | 低 | 中 |
| 同一关系在多个模型中复用 | 重复 | 集中管理 |
| 后续修改关系 | 更新多个 `resolve_*` | 改一处声明 |
| GraphQL 和 MCP 复用 | 单独处理 | 自然延伸 |

## 目标

同样的 `Sprint -> Task -> User` 场景。输出与 Core API 版本完全相同 —— 区别在于 `resolve_owner` 和 `resolve_tasks` 从视图模型中消失了。

## Step 1：定义带关系的实体

关系声明从视图模型移到实体类中：

```python
from pydantic_resolve import Relationship, base_entity, config_global_resolver


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
```

## Step 2：创建 AutoLoad 并配置解析器

```python
diagram = BaseEntity.get_diagram()
AutoLoad = diagram.create_auto_load()
config_global_resolver(diagram)
```

这三行把 ERD 接入解析器。`AutoLoad` 将图表特定的元数据嵌入到注解中。

## Step 3：用 AutoLoad 注解替换 resolve_*

视图模型继承自实体。关系字段用 `AutoLoad()` 替代 `resolve_*`：

```python
class TaskView(TaskEntity):
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None  # (1)


class SprintView(SprintEntity):
    tasks: Annotated[list[TaskView], AutoLoad()] = []
    task_count: int = 0

    def post_task_count(self):  # (2)
        return len(self.tasks)
```

1.  `AutoLoad()` 从图表中查找 `name='owner'` 的 `Relationship`，并在分析时生成等效的 `resolve_owner`。
2.  `post_*` 保持不变 —— ERD 消除的是关系连线，不是业务特定的后处理。

## Step 4：运行解析器

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
 ],
 'task_count': 2}
{'id': 2, 'name': 'Sprint 25',
 'tasks': [
     {'id': 12, 'title': 'Bug fixes', 'owner_id': 7, 'owner': {'id': 7, 'name': 'Ada'}},
 ],
 'task_count': 1}
```

## 变化了什么

与 Core API 版本相比：

- `resolve_owner` 消失了。
- `resolve_tasks` 消失了。
- 关系声明集中在一个地方（`__relationships__`）。
- `post_task_count` 保持不变。

## AutoLoad 如何工作

`AutoLoad` 不是魔法。解析器扫描类时：

1. 在字段上找到 `AutoLoad()` 注解。
2. 按名称从图表中查找对应的 `Relationship`。
3. 生成等效的 `resolve_*` 方法，用 FK 值调用 loader。

如果字段名与关系名不匹配，使用 `origin` 参数：

```python
class SprintView(SprintEntity):
    items: Annotated[list[TaskView], AutoLoad(origin='tasks')] = []
```

## 声明 ERD 的两种方式

### 内联 `__relationships__` 在实体类上

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

适合关系元数据自然属于实体类型的场景。

### 外部 `ErDiagram(...)` 声明

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

适合不想修改实体类，或同一类在多个模块中共享的场景。

!!! warning "一个项目只用一个 Diagram"

    使用外部 `ErDiagram(...)` 时，所有实体类会注册到共享的内部 registry。多个 `ErDiagram` 实例注册同一实体会导致不可预测的结果。

    如需合并不同来源的关系，使用 `add_relationship()`：

    ```python
    diagram = ErDiagram(entities=[...])
    diagram = diagram.add_relationship(more_entities)
    ```

## 关系类型

### 一对一

```python
Relationship(
    fk='owner_id',
    name='owner',
    target=UserEntity,
    loader=user_loader
)
```

### 一对多

```python
Relationship(
    fk='id',
    name='tasks',
    target=list[TaskEntity],
    loader=task_loader
)
```

### 处理 None FK 值

```python
Relationship(
    fk='owner_id',
    name='owner',
    target=UserEntity,
    loader=user_loader,
    fk_none_default=None
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

### 同一 FK 的多个关系

```python
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='owner_id', name='author', target=UserEntity, loader=user_loader),
        Relationship(fk='owner_id', name='reviewer', target=UserEntity, loader=reviewer_loader),
    ]
    id: int
    owner_id: int
```

### 使用 fk_fn 自定义 FK 转换

```python
Relationship(
    fk='tag_ids',             # 逗号分隔字符串 "1,2,3"
    name='tags',
    target=list[TagEntity],
    loader=tag_loader,
    load_many=True,
    load_many_fn=lambda ids: ids.split(',') if ids else []
)
```

## 从手写 resolve_* 迁移到 ERD

迁移路径是增量式的：

1. 定义镜像现有响应模型的实体。
2. 添加 `__relationships__` 或外部 `ErDiagram` 声明。
3. 创建 `AutoLoad` 和 `config_global_resolver`。
4. 用 `AutoLoad()` 注解替换 `resolve_*` 方法。
5. 保持 `post_*` 方法不变。

你可以在同一项目中混合手写和 ERD 驱动的解析：

```python
class TaskView(TaskEntity):
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None  # ERD 驱动
    comments: list[CommentView] = []

    def resolve_comments(self, loader=Loader(comment_loader)):  # 手写
        return loader.load(self.id)
```

## 自定义解析器

如果你不想使用全局解析器：

```python
from pydantic_resolve import config_resolver

MyResolver = config_resolver('MyResolver', er_diagram=diagram)
result = await MyResolver().resolve(data)
```

## 处理循环导入

### 同模块字符串引用

```python
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='owner_id', name='owner', target='UserEntity', loader=user_loader)
    ]
```

### 跨模块引用

```python
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(
            fk='owner_id',
            target='app.models.user:UserEntity',
            name='owner',
            loader=user_loader
        )
    ]
```

支持的格式：

- 简单类名：`'UserEntity'`
- 模块路径语法：`'app.models.user:UserEntity'`
- 列表泛型：`list['UserEntity']` 或 `list['app.models.user:UserEntity']`

## 何时还不适合使用 ERD

在以下场景继续使用手写 Core API：

- 你只有少数几个响应模型
- 关系结构仍在快速变化
- 重复成本还不是真实问题

ERD 是扩展步骤，不是必经之路。

## 下一步

- [ERD 与 DefineSubset](./erd_define_subset.zh.md) —— 从响应中隐藏内部 FK 字段。
- [DataLoader 深入](./dataloader_deep_dive.zh.md) —— 了解批处理在底层的工作原理。
