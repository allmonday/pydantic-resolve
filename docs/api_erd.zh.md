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

### create_auto_load()

```python
AutoLoad = diagram.create_auto_load() -> Callable
```

创建绑定到此图表的注解工厂。在 `Annotated` 类型提示中使用。

### add_relationship()

```python
merged = diagram.add_relationship(entities: list[Entity]) -> ErDiagram
```

将外部实体（例如来自 ORM）合并到图表中。返回新的 `ErDiagram`。

## AutoLoad

```python
AutoLoad(origin: str | None = None)
```

通过 ERD 关系自动解析字段的注解。

```python
class TaskView(TaskEntity):
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
    # 或使用显式关系名称：
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

```python
from pydantic_resolve import query

@query(name: str | None = None)
async def get_all(cls, **kwargs) -> list[Entity]: ...
```

## @mutation 装饰器

```python
from pydantic_resolve import mutation

@mutation(name: str | None = None)
async def create(cls, **kwargs) -> Entity: ...
```
