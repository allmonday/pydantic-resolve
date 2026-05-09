# ER 图 API

[English](./api_erd.md)

## base_entity

```python
from pydantic_resolve import base_entity

BaseEntity = base_entity() -> type
```

创建一个自动从子类收集 `__relationships__` 的基类。调用 `BaseEntity.get_diagram()` 获取结果 `ErDiagram`。

```python
BaseEntity = base_entity()

class UserEntity(BaseModel, BaseEntity):
    id: int
    name: str

class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='owner_id', target=UserEntity, name='owner', loader=user_loader)
    ]
    id: int
    owner_id: int

diagram = BaseEntity.get_diagram()
```

## Relationship

```python
from pydantic_resolve import Relationship

Relationship(
    fk: str,
    target: Any,
    name: str,
    loader: Callable | None = None,
    fk_fn: Callable | None = None,
    fk_none_default: Any | None = None,
    fk_none_default_factory: Callable | None = None,
    load_many: bool = False,
    load_many_fn: Callable | None = None,
)
```

| 参数 | 类型 | 描述 |
|-----------|------|-------------|
| `fk` | `str` | 实体上的外键字段名 |
| `target` | `Any` | 目标实体类（一对多关系使用 `list[Entity]`） |
| `name` | `str` | **必填。**唯一的关系名称 |
| `loader` | `Callable \| None` | DataLoader 函数 |
| `fk_fn` | `Callable \| None` | 在传递给 loader 之前转换 FK 值 |
| `fk_none_default` | `Any \| None` | FK 为 None 时的默认值 |
| `fk_none_default_factory` | `Callable \| None` | FK 为 None 时默认值的工厂函数 |
| `load_many` | `bool` | FK 字段包含多个值 |
| `load_many_fn` | `Callable \| None` | 将 FK 字段转换为可迭代对象用于 load_many |

## Entity

```python
from pydantic_resolve import Entity

Entity(
    kls: type[BaseModel],
    relationships: list[Relationship] = [],
    queries: list[QueryConfig] = [],
    mutations: list[MutationConfig] = [],
)
```

| 参数 | 类型 | 描述 |
|-----------|------|-------------|
| `kls` | `type[BaseModel]` | Pydantic 模型类 |
| `relationships` | `list[Relationship]` | 出站关系 |
| `queries` | `list[QueryConfig]` | GraphQL 查询入口点 |
| `mutations` | `list[MutationConfig]` | GraphQL 变更入口点 |

## ErDiagram

```python
from pydantic_resolve import ErDiagram

ErDiagram(
    entities: list[Entity],
    description: str | None = None,
)
```

| 参数 | 类型 | 描述 |
|-----------|------|-------------|
| `entities` | `list[Entity]` | 所有实体定义 |
| `description` | `str \| None` | 可选的图表描述 |

### add_relationship()

```python
merged = diagram.add_relationship(entities: list[Entity]) -> ErDiagram
```

将外部实体（例如来自 ORM）合并到图表中。返回新的 `ErDiagram`。

### 外部 diagram 歧义

`base_entity()` 生成的 diagram 只服务于一组模型，关系查找天然只有一个来源，因此不会出现这类歧义。

外部 `ErDiagram` 不一样。如果同一个模型类同时出现在多个外部 `ErDiagram` 中，并且这些 diagram 为同一个关系 `name` 配置了不同的 `fk`，现在 `pydantic-resolve` 会直接抛出 `ValueError`，而不是像过去那样静默采用“最后一次注册”的配置。

这个约束主要影响那些需要在 resolver 之外推断关系元数据的场景，尤其是：

- `DefineSubset` 自动补隐藏 FK 字段
- 通过字段名触发的隐式关系解析
- subset 额外字段上的显式 `AutoLoad(origin=...)`

下面是一个会报歧义的例子：

```python
ErDiagram(entities=[
    Entity(kls=TaskEntity, relationships=[
        Relationship(fk='owner_id', target=UserEntity, name='user', loader=user_loader),
    ])
])

ErDiagram(entities=[
    Entity(kls=TaskEntity, relationships=[
        Relationship(fk='manager_id', target=UserEntity, name='user', loader=user_loader),
    ])
])

class TaskSummary(DefineSubset):
    __subset__ = (TaskEntity, ('id',))
    user: Optional[UserEntity] = None

# 抛出 ValueError: ambiguous external ErDiagram relationship "user"
```

避免歧义的方式有四种：

- 优先使用 `base_entity()` + `BaseEntity.get_diagram()`，让一组模型只有一个权威 diagram。
- 对同一个模型类和关系名，只保留一个权威的外部 `ErDiagram` 配置。
- 如果必须维护多个外部 diagram，不要在同一个模型类上复用相同的关系名去表达不同的 FK 语义。
- 对 `DefineSubset`，如果你不希望 subset 构建阶段自动推断 FK，就把 FK 字段显式选进来。

## AutoLoad

```python
AutoLoad(origin: str | None = None)
```

通过 ERD 关系自动解析字段的注解。

如果字段名已经和 `Relationship.name` 一致，通常根本不需要写 `AutoLoad()`：

```python
class TaskView(TaskEntity):
    owner: Optional[UserEntity] = None
```

只有当字段名和关系名不一致时，才需要使用 `AutoLoad(origin=...)`。

```python
class TaskView(TaskEntity):
    # 显式映射到关系名 `owner`
    my_owner: Annotated[Optional[UserEntity], AutoLoad(origin='owner')] = None

    # 显式映射到关系名 `tasks`
    items: Annotated[list[TaskEntity], AutoLoad(origin='tasks')] = []
```

| 参数 | 类型 | 描述 |
|-----------|------|-------------|
| `origin` | `str \| None` | 要查找的关系名称。默认为字段名。 |

## QueryConfig

```python
from pydantic_resolve import QueryConfig

QueryConfig(
    method: Callable,
    name: str | None = None,
    description: str | None = None,
)
```

## MutationConfig

```python
from pydantic_resolve import MutationConfig

MutationConfig(
    method: Callable,
    name: str | None = None,
    description: str | None = None,
)
```

## @query 装饰器

必须作为方法装饰器**用在 Pydantic 实体类内部**，不能装饰独立函数。

```python
from pydantic_resolve import query

class SprintEntity(BaseModel, BaseEntity):
    id: int
    name: str

    @query
    async def get_all(cls, limit: int = 20) -> list['SprintEntity']:
        return await fetch_sprints(limit)
```

GraphQL 字段名会根据实体名和方法名自动生成。
如果需要覆盖其中的方法名部分，请使用 `QueryConfig(name=...)`。

## @mutation 装饰器

必须作为方法装饰器**用在 Pydantic 实体类内部**，不能装饰独立函数。

```python
from pydantic_resolve import mutation

class SprintEntity(BaseModel, BaseEntity):
    id: int
    name: str

    @mutation
    async def create(cls, name: str) -> 'SprintEntity':
        return await db.create_sprint(name=name)
```

GraphQL 字段名会根据实体名和方法名自动生成。
如果需要覆盖其中的方法名部分，请使用 `MutationConfig(name=...)`。
