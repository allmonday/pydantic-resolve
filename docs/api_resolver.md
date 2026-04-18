# Resolver API

[中文版](./api_resolver.zh.md)

## Resolver

The main entry point for pydantic-resolve. It walks a tree of Pydantic models, executes `resolve_*` and `post_*` methods, and manages DataLoader batching.

```python
from pydantic_resolve import Resolver

class Resolver:
    def __init__(
        self,
        loader_params: dict[Any, dict[str, Any]] | None = None,
        global_loader_param: dict[str, Any] | None = None,
        loader_instances: dict[Any, Any] | None = None,
        context: dict[str, Any] | None = None,
        ensure_type: bool = False,
        debug: bool = False,
        enable_from_attribute_in_type_adapter: bool = False,
        annotation: type[T] | None = None,
        split_loader_by_type: bool = False,
    )
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `loader_params` | `dict \| None` | `None` | Per-loader configuration keyed by loader class |
| `global_loader_param` | `dict \| None` | `None` | Parameters applied to all loaders |
| `loader_instances` | `dict \| None` | `None` | Pre-created DataLoader instances |
| `context` | `dict \| None` | `None` | Global context dict accessible in all methods |
| `ensure_type` | `bool` | `False` | Validate return values match field type annotations |
| `debug` | `bool` | `False` | Print per-node timing information |
| `enable_from_attribute_in_type_adapter` | `bool` | `False` | Enable Pydantic v2 `from_attributes` mode |
| `annotation` | `type \| None` | `None` | Explicit root type when input is a list of Union types |
| `split_loader_by_type` | `bool` | `False` | Create separate DataLoader instances per `request_type`. **Incompatible with `loader_instances`**. |

#### split_loader_by_type

When multiple fields in the same resolve tree share a `DataLoader` but declare different response types (e.g., `TaskCard` with 2 columns vs `TaskDetail` with 20 columns), the default behavior creates a single shared loader instance whose `_query_meta.fields` is the **union** of all requested columns. This means even the lightweight view queries all 20 columns.

Setting `split_loader_by_type=True` creates an independent `DataLoader` instance per `request_type`, so each instance's `_query_meta` contains only the columns its target type actually needs.

```python
class Dashboard(BaseModel):
    id: int
    cards: List[TaskCard] = []       # only needs id, title
    details: List[TaskDetail] = []   # needs id, title, desc, status, ...

    def resolve_cards(self, loader=Loader(TaskLoader)):
        return loader.load(self.id)

    def resolve_details(self, loader=Loader(TaskLoader)):
        return loader.load(self.id)

# Default: one TaskLoader instance, _query_meta.fields = union of all columns
# Split:   two TaskLoader instances, each with its own _query_meta
result = await Resolver(split_loader_by_type=True).resolve(Dashboard(id=1))
```

**Limitation:** Split loaders maintain independent caches. If both `cards` and `details` request the same key `1`, the database will be queried twice — once by each loader instance.

**Incompatible with `loader_instances`:** Pre-created instances are shared by nature and cannot be split per type. Raises `ValueError` if both are provided.

### resolve()

```python
async def resolve(self, data: T) -> T
```

Walks the model tree, executes all `resolve_*` and `post_*` methods, and returns the fully resolved data.

### loader_instance_cache

After resolution, contains all DataLoader instances that were created:

```python
resolver = Resolver()
result = await resolver.resolve(data)

# Default mode: dict[str, DataLoader]
#   {'module.TaskLoader': <DataLoader>}
print(resolver.loader_instance_cache['module.TaskLoader'])
```

When `split_loader_by_type=True`, the structure is nested:

```python
# Split mode: dict[str, dict[tuple[type, ...], DataLoader]]
#   {'module.TaskLoader': {(TaskCard,): inst1, (TaskDetail,): inst2}}
print(resolver.loader_instance_cache['module.TaskLoader'][(TaskCard,)])
```

## config_global_resolver

```python
from pydantic_resolve import config_global_resolver

config_global_resolver(er_diagram: ErDiagram | None = None) -> None
```

Injects an ERD into the default `Resolver` class globally. After calling this, `Resolver()` will use the ERD for `AutoLoad` resolution.

## config_resolver

```python
from pydantic_resolve import config_resolver

CustomResolver = config_resolver(
    name: str | None = None,
    er_diagram: ErDiagram | None = None,
) -> type[Resolver]
```

Creates a new Resolver class with specific ERD configuration. Use this when you need multiple resolver configurations in the same process.

```python
BlogResolver = config_resolver('BlogResolver', er_diagram=blog_diagram)
ShopResolver = config_resolver('ShopResolver', er_diagram=shop_diagram)
```

## reset_global_resolver

```python
from pydantic_resolve import reset_global_resolver

reset_global_resolver() -> None
```

Resets the global resolver to its default state (no ERD).

## resolve_* Methods

Methods following the pattern `resolve_<field_name>` on Pydantic models. They describe how to fetch missing data.

```python
class TaskView(BaseModel):
    owner: Optional[UserView] = None

    def resolve_owner(self, loader=Loader(user_loader)):
        return loader.load(self.owner_id)
```

### Supported Parameters

| Parameter | Description |
|-----------|-------------|
| `loader=Loader(fn)` | DataLoader dependency |
| `context` | Global context from `Resolver(context=...)` |
| `ancestor_context` | Dict of exposed ancestor values |
| `parent` | Direct parent node reference |

Methods can be sync or async. Return values are recursively resolved.

## post_* Methods

Methods following the pattern `post_<field_name>`. They run after descendant data is ready.

```python
class SprintView(BaseModel):
    tasks: list[TaskView] = []
    task_count: int = 0

    def post_task_count(self):
        return len(self.tasks)
```

### Supported Parameters

| Parameter | Description |
|-----------|-------------|
| `context` | Global context from `Resolver(context=...)` |
| `ancestor_context` | Dict of exposed ancestor values |
| `parent` | Direct parent node reference |
| `loader=Loader(fn)` | DataLoader dependency (rarely needed) |
| `collector=Collector('name')` | Aggregated descendant data |

Return values are **not** recursively resolved.

## post_default_handler

A special method that runs after all other `post_*` methods. It does not auto-assign — you must set fields manually:

```python
class SprintView(BaseModel):
    task_count: int = 0
    summary: str = ""

    def post_task_count(self):
        return len(self.tasks)

    def post_default_handler(self):
        self.summary = f"{self.task_count} tasks"
```
