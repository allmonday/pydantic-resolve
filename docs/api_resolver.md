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
print(resolver.loader_instance_cache)
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
