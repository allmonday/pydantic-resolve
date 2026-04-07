# Cross-Layer Annotations

[中文版](./api_cross_layer.zh.md)

## ExposeAs

```python
from pydantic_resolve import ExposeAs

ExposeAs(alias: str)
```

Exposes a field's value to descendant nodes under the given alias. Descendants can read it via `ancestor_context`.

```python
class SprintView(BaseModel):
    name: Annotated[str, ExposeAs('sprint_name')]

class TaskView(BaseModel):
    def post_full_title(self, ancestor_context):
        return f"{ancestor_context['sprint_name']} / {self.title}"
```

Aliases should be globally unique within the resolved tree.

## SendTo

```python
from pydantic_resolve import SendTo

SendTo(name: str | tuple[str, ...])
```

Marks a field's value to be sent upward to a parent collector. Accepts a single collector name or a tuple of names.

```python
# Single target
class TaskView(BaseModel):
    owner: Annotated[Optional[User], SendTo('contributors')] = None

# Multiple targets
class TaskView(BaseModel):
    owner: Annotated[Optional[User], SendTo(('contributors', 'all_users'))] = None
```

## Collector

```python
from pydantic_resolve import Collector

Collector(alias: str, flat: bool = False)
```

Collects values from descendant nodes marked with `SendTo`. Used in `post_*` methods.

```python
class SprintView(BaseModel):
    contributors: list[User] = []

    def post_contributors(self, collector=Collector('contributors')):
        return collector.values()
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `alias` | `str` | required | Must match the `SendTo` name |
| `flat` | `bool` | `False` | Use `extend` instead of `append` for list values |

### flat parameter

- `flat=False`: `collector.values()` → `[UserA, [UserB, UserC]]`
- `flat=True`: `collector.values()` → `[UserA, UserB, UserC]`

## ICollector

```python
from pydantic_resolve import ICollector

class ICollector:
    alias: str

    def add(self, val) -> None: ...
    def values(self) -> Any: ...
```

Base interface for custom collectors. Implement `add` and `values`:

```python
class CounterCollector(ICollector):
    def __init__(self, alias):
        self.alias = alias
        self.counter = 0

    def add(self, val):
        self.counter += len(val) if isinstance(val, list) else 1

    def values(self):
        return self.counter
```
