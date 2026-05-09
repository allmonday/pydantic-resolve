# DefineSubset API

[English](./api_subset.md)

## DefineSubset

```python
from pydantic_resolve import DefineSubset

class MySubset(DefineSubset):
    __subset__ = (SourceEntity, ('field1', 'field2'))
    # 或
    __subset__ = SubsetConfig(kls=SourceEntity, fields=['field1', 'field2'])
```

从源实体创建一个包含选定字段的新 Pydantic 模型。你可以在其上添加额外字段（包括 `AutoLoad` 注解）。

如果新增字段对应一个 ERD 关系，`DefineSubset` 会在需要时自动把所需的 FK 字段补成一个隐藏的 `exclude=True` 字段。下面两种情况都适用：

- 字段名与关系名一致时的隐式匹配
- 使用 `AutoLoad(origin=...)` 的显式别名

例如：

```python
class TaskCard(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'title'))

    # 字段名和关系名 `owner` 不一致
    my_owner: Annotated[Optional[UserEntity], AutoLoad(origin='owner')] = None
```

即使 `owner_id` 不在 subset 字段列表中，`DefineSubset` 仍会在内部补上它，这样自动生成的 resolve 方法才能继续加载 `my_owner`。

### 外部 ErDiagram 约束

当 `DefineSubset` 依赖外部 `ErDiagram(...)`，而不是 `base_entity()` 时，它可能需要在 resolver 实例创建之前就推断 FK 字段。

如果多个外部 diagram 为同一个模型类注册了同一个关系名，但使用了不同的 `fk` 值，subset 构建阶段就没有办法判断该选哪一个，因此现在会直接抛出 `ValueError`。

建议对每个 `(模型类, 关系名)` 只保留一个权威的外部关系定义；如果你不想让 subset 去推断隐藏 FK，也可以直接把 FK 字段显式选进 subset。

### 元组形式

```python
class TaskSummary(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'title'))
```

等价于 `SubsetConfig(kls=TaskEntity, fields=['id', 'title'])`。

## SubsetConfig

```python
from pydantic_resolve import SubsetConfig

SubsetConfig(
    kls: type[BaseModel],
    fields: list[str] | Literal["all"] | None = None,
    omit_fields: list[str] | None = None,
    expose_as: list[tuple[str, str]] | None = None,
    send_to: list[tuple[str, tuple[str, ...] | str]] | None = None,
    excluded_fields: list[str] | None = None,
)
```

| 参数 | 类型 | 描述 |
|-----------|------|-------------|
| `kls` | `type[BaseModel]` | 源实体类 |
| `fields` | `list[str] \| "all" \| None` | 要包含的字段（与 `omit_fields` 互斥） |
| `omit_fields` | `list[str] \| None` | 要排除的字段（与 `fields` 互斥） |
| `expose_as` | `list[tuple[str, str]] \| None` | ExposeAs 的 `(字段名, 别名)` 对 |
| `send_to` | `list[tuple[str, str \| tuple]] \| None` | SendTo 的 `(字段名, 收集器名称)` 对 |
| `excluded_fields` | `list[str] \| None` | 标记为 `Field(exclude=True)` 的字段 |

### 包含所有选项的示例

```python
class TaskSummary(DefineSubset):
    __subset__ = SubsetConfig(
        kls=TaskEntity,
        fields=['id', 'title', 'name'],
        expose_as=[('name', 'task_name')],
        send_to=[('id', 'task_ids')],
        excluded_fields=['internal_flag'],
    )
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
```
