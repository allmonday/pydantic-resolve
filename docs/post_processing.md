# Post Processing

[中文版](./post_processing.zh.md)

`resolve_*` loads missing data. `post_*` is for everything that should happen **after** the current subtree is already assembled.

This distinction matters. If the reader does not understand it early, `post_*` quickly starts to look like a second, mysterious loading hook. It is not.

## Extend the Same Sprint Example

Now that `Sprint -> Task -> User` can already be resolved, we can derive two fields from the finished subtree:

- `task_count`
- `contributor_names`

```python
import asyncio
from typing import Optional

from pydantic import BaseModel
from pydantic_resolve import Loader, Resolver, build_list, build_object


# --- Fake database ---
USERS = {
    7: {"id": 7, "name": "Ada"},
    8: {"id": 8, "name": "Bob"},
    9: {"id": 9, "name": "Cara"},
}

TASKS = [
    {"id": 10, "title": "Design docs", "sprint_id": 1, "owner_id": 7},
    {"id": 11, "title": "Refine examples", "sprint_id": 1, "owner_id": 8},
    {"id": 12, "title": "Write tests", "sprint_id": 1, "owner_id": 7},
]


async def user_loader(user_ids: list[int]):
    users = [USERS.get(uid) for uid in user_ids]
    return build_object(users, user_ids, lambda u: u.id)


async def task_loader(sprint_ids: list[int]):
    tasks = [t for t in TASKS if t["sprint_id"] in sprint_ids]
    return build_list(tasks, sprint_ids, lambda t: t["sprint_id"])


class UserView(BaseModel):
    id: int
    name: str


class TaskView(BaseModel):
    id: int
    title: str
    owner_id: int
    owner: Optional[UserView] = None

    def resolve_owner(self, loader=Loader(user_loader)):
        return loader.load(self.owner_id)


class SprintView(BaseModel):
    id: int
    name: str
    tasks: list[TaskView] = []
    task_count: int = 0
    contributor_names: list[str] = []

    def resolve_tasks(self, loader=Loader(task_loader)):
        return loader.load(self.id)

    def post_task_count(self):
        return len(self.tasks)

    def post_contributor_names(self):
        return sorted({task.owner.name for task in self.tasks if task.owner})


# --- Resolve ---
raw_sprints = [{"id": 1, "name": "Sprint 24"}]
sprints = [SprintView.model_validate(s) for s in raw_sprints]
sprints = await Resolver().resolve(sprints)

print(sprints[0].model_dump())
# {'id': 1, 'name': 'Sprint 24',
#  'tasks': [
#      {'id': 10, 'title': 'Design docs', 'owner_id': 7, 'owner': {'id': 7, 'name': 'Ada'}},
#      {'id': 11, 'title': 'Refine examples', 'owner_id': 8, 'owner': {'id': 8, 'name': 'Bob'}},
#      {'id': 12, 'title': 'Write tests', 'owner_id': 7, 'owner': {'id': 7, 'name': 'Ada'}},
#  ],
#  'task_count': 3,
#  'contributor_names': ['Ada', 'Bob']}
```

## Execution Order

For one sprint, the lifecycle looks like this:

```mermaid
flowchart LR
    a["resolve_tasks"] --> b["TaskView.resolve_owner"]
    b --> c["post_task_count"]
    c --> d["post_contributor_names"]
```

The exact implementation can be async under the hood, but the mental model is simple:

1. Load descendants first (all `resolve_*` methods).
2. Run `post_*` only after descendant data is ready.

That timing is why `post_*` is ideal for summary fields, formatting, and business-specific derived values.

## Rule of Thumb

| Question | `resolve_*` | `post_*` |
|---|---|---|
| Needs external IO? | Yes | Usually no |
| Runs before descendants are ready? | Yes | No |
| Good for counts, labels, formatting? | Sometimes | Yes |
| Return value is resolved again? | Yes | No |

## What `post_*` Is Good At

Typical uses include:

- **Counts and totals**: `task_count`, `total_price`, `unread_count`
- **Sorted display fields**: `contributor_names`, `sorted_tags`
- **Deduplicated labels**: `unique_categories`
- **String formatting**: `full_title`, `display_name`
- **Business summaries** that should not require another query

### Example: Formatting

```python
class TaskView(BaseModel):
    id: int
    title: str
    priority: int
    priority_label: str = ""

    def post_priority_label(self):
        labels = {1: "Low", 2: "Medium", 3: "High"}
        return labels.get(self.priority, "Unknown")
```

### Example: Enrichment from Nested Data

```python
class SprintView(BaseModel):
    id: int
    name: str
    tasks: list[TaskView] = []
    has_overdue: bool = False

    def resolve_tasks(self, loader=Loader(task_loader)):
        return loader.load(self.id)

    def post_has_overdue(self):
        return any(t.due_date < date.today() for t in self.tasks)
```

### Example: Aggregation

```python
class OrderView(BaseModel):
    id: int
    items: list[OrderItem] = []
    total: float = 0.0

    def resolve_items(self, loader=Loader(item_loader)):
        return loader.load(self.id)

    def post_total(self):
        return sum(item.price * item.quantity for item in self.items)
```

## What `post_*` Is Not For

Avoid using `post_*` as a hidden relationship loader. If a field needs external data, keep that behavior in `resolve_*`.

That separation keeps the code readable:

- `resolve_*` answers: **where does the missing data come from?**
- `post_*` answers: **what do we do with the data after it is ready?**

```python
# BAD: loading data in post_*
def post_owner(self, loader=Loader(user_loader)):  # don't do this
    return loader.load(self.owner_id)

# GOOD: load in resolve_*, transform in post_*
def resolve_owner(self, loader=Loader(user_loader)):
    return loader.load(self.owner_id)

def post_owner_display(self):
    return f"{self.owner.name} ({self.owner.email})"
```

## post_* Parameters

`post_*` methods can accept additional parameters beyond the basic form:

### context

Access the global context dict passed to `Resolver`:

```python
class SprintView(BaseModel):
    tasks: list[TaskView] = []
    visible_task_count: int = 0

    def resolve_tasks(self, loader=Loader(task_loader)):
        return loader.load(self.id)

    def post_visible_task_count(self, context):
        user_role = context.get('role', 'viewer')
        if user_role == 'admin':
            return len(self.tasks)
        return len([t for t in self.tasks if t.visible])
```

### parent

Access the direct parent node. Useful for tree structures:

```python
class TreeNode(BaseModel):
    name: str
    children: list[TreeNode] = []
    depth: int = 0

    def post_depth(self, parent):
        if parent is None:
            return 0
        return parent.depth + 1
```

### ancestor_context

Access data exposed by ancestors via `ExposeAs` (covered in [Cross-Layer Data Flow](./cross_layer_data_flow.md)):

```python
class TaskView(BaseModel):
    title: str
    full_title: str = ""

    def post_full_title(self, ancestor_context):
        sprint_name = ancestor_context.get('sprint_name', '')
        return f"{sprint_name} / {self.title}"
```

### collector

Collect data from descendant nodes via `SendTo` (covered in [Cross-Layer Data Flow](./cross_layer_data_flow.md)):

```python
class SprintView(BaseModel):
    tasks: list[TaskView] = []
    contributors: list[UserView] = []

    def resolve_tasks(self, loader=Loader(task_loader)):
        return loader.load(self.id)

    def post_contributors(self, collector=Collector('contributors')):
        return collector.values()
```

## post_default_handler

A special post method that runs after all other `post_*` methods. It does not do automatic assignment — you must set fields manually:

```python
class SprintView(BaseModel):
    tasks: list[TaskView] = []
    task_count: int = 0
    summary: str = ""

    def post_task_count(self):
        return len(self.tasks)

    def post_default_handler(self):
        # runs after post_task_count
        self.summary = f"{self.task_count} tasks in this sprint"
```

## A Useful Boundary

`post_*` can accept advanced parameters such as `context`, `parent`, `ancestor_context`, and `collector`. But those features are easier to understand after the basic timing model is already clear.

## When to Stop Here

The `resolve_*` + `post_*` combination covers the majority of data assembly needs. Most endpoints never need more than this.

Move on to [Cross-Layer Data Flow](./cross_layer_data_flow.md) only when you encounter parent-child coordination that manual traversal cannot handle cleanly.

## Next

Continue to [Cross-Layer Data Flow](./cross_layer_data_flow.md) to see how ancestors and descendants can coordinate without explicit traversal code.
