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
