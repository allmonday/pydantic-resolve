# Cross-Layer Data Flow

[中文版](./cross_layer_data_flow.zh.md) | [docs](./index.md)

Most users do not need these features on day one. But when parent and child nodes need to coordinate across multiple layers, `ExposeAs`, `SendTo`, and `Collector` let you keep that logic declarative instead of writing manual traversal code.

We will stay on the same `Sprint -> Task -> User` scenario.

## Two Problems We Want to Solve

1. Each task should build a `full_title` like `Sprint 24 / Design docs`.
2. The sprint should aggregate all task owners into `contributors`.

Both problems cross object boundaries. That is exactly where cross-layer flow starts to pay off.

## Full Example

```python
from typing import Annotated, Optional

from pydantic import BaseModel
from pydantic_resolve import Collector, ExposeAs, Loader, SendTo


class SprintView(BaseModel):
	id: int
	name: Annotated[str, ExposeAs('sprint_name')]
	tasks: list['TaskView'] = []
	contributors: list['UserView'] = []

	def resolve_tasks(self, loader=Loader(task_loader)):
		return loader.load(self.id)

	def post_contributors(self, collector=Collector('contributors')):
		return collector.values()


class TaskView(BaseModel):
	id: int
	title: str
	owner_id: int
	owner: Annotated[Optional['UserView'], SendTo('contributors')] = None
	full_title: str = ""

	def resolve_owner(self, loader=Loader(user_loader)):
		return loader.load(self.owner_id)

	def post_full_title(self, ancestor_context):
		return f"{ancestor_context['sprint_name']} / {self.title}"
```

## Downward Flow with `ExposeAs`

`ExposeAs('sprint_name')` means the `SprintView.name` field is published to descendants under the alias `sprint_name`.

That is why `TaskView.post_full_title` can read:

```python
ancestor_context['sprint_name']
```

Use this when descendants need ancestor context such as:

- sprint names
- tenant identifiers
- permission scopes
- display prefixes

### Practical Rule

Expose aliases should be globally unique within the resolved tree. If different ancestors reuse the same alias for unrelated meanings, the result becomes hard to reason about.

## Upward Flow with `SendTo` and `Collector`

`SendTo('contributors')` marks `TaskView.owner` as data that should flow upward into a collector named `contributors`.

`SprintView.post_contributors` is where the sprint consumes that aggregated data:

```python
def post_contributors(self, collector=Collector('contributors')):
	return collector.values()
```

Use this when a parent needs a summary derived from descendants, for example:

- all contributors
- all tags used under a subtree
- all related users touched by nested nodes

## Lifecycle Mental Model

The cross-layer version still follows the same two-phase discipline:

1. ancestor data is exposed downward
2. descendants resolve and post-process themselves
3. descendant values are sent upward
4. parent `post_*` methods consume the collected values

The important point is that you still are not writing manual tree traversal code.

## When These Features Are Worth It

Reach for them when:

- children need ancestor context and passing it explicitly would clutter signatures everywhere
- parents need aggregated descendant data and manual loops would spread across endpoint code

Skip them when:

- a field can be computed locally inside the current node
- only one layer is involved
- the explicit version is still short and obvious

## Next

Continue to [ERD and AutoLoad](./erd_and_autoload.md) when repeated `resolve_*` wiring starts to appear across many models.