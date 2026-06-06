# Post Processing

[中文版](./post_processing.zh.md)

`resolve_*` loads missing data. `post_*` computes derived fields — values that depend on the fully assembled subtree, such as counts, summaries, and formatted strings.

## Goal

Building on the `Sprint -> Task -> User` tree from Core API, you now want each sprint to include:

- `task_count` — the number of tasks in that sprint
- `contributor_names` — deduplicated, sorted names of all owners

```json
[
    {
        "id": 1,
        "name": "Sprint 24",
        "tasks": [
            {"id": 10, "title": "Design docs", "owner": {"id": 7, "name": "Ada"}},
            {"id": 11, "title": "Refine examples", "owner": {"id": 8, "name": "Bob"}},
            {"id": 12, "title": "Write tests", "owner": {"id": 7, "name": "Ada"}}
        ],
        "task_count": 3,
        "contributor_names": ["Ada", "Bob"]
    },
    {
        "id": 2,
        "name": "Sprint 25",
        "tasks": [
            {"id": 13, "title": "Bug fixes", "owner": {"id": 7, "name": "Ada"}}
        ],
        "task_count": 1,
        "contributor_names": ["Ada"]
    }
]
```

These fields don't come from a loader — they're derived from data already on each sprint. The resolver computes them for every sprint in the list.

## Step 1: Add post_* Methods

Add `post_task_count` and `post_contributor_names` to the same `SprintView`:

```python
class SprintView(BaseModel):
    id: int
    name: str
    tasks: list[TaskView] = []
    task_count: int = 0  # (1)
    contributor_names: list[str] = []

    def resolve_tasks(self, loader=Loader(task_loader)):
        return loader.load(self.id)

    def post_task_count(self):  # (2)
        return len(self.tasks)

    def post_contributor_names(self):
        return sorted({task.owner.name for task in self.tasks if task.owner})
```

1.  Derived fields start with a default value, just like `resolve_*` fields start as `None`.
2.  Method name follows `post_<field_name>`. The return value is assigned to the matching field.

## Step 2: Run the Resolver

The same `Resolver().resolve()` call handles everything:

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

Output:

```python
{'id': 1, 'name': 'Sprint 24',
 'tasks': [
     {'id': 10, 'title': 'Design docs', 'owner_id': 7, 'owner': {'id': 7, 'name': 'Ada'}},
     {'id': 11, 'title': 'Refine examples', 'owner_id': 8, 'owner': {'id': 8, 'name': 'Bob'}},
     {'id': 12, 'title': 'Write tests', 'owner_id': 7, 'owner': {'id': 7, 'name': 'Ada'}},
 ],
 'task_count': 3,
 'contributor_names': ['Ada', 'Bob']}
{'id': 2, 'name': 'Sprint 25',
 'tasks': [
     {'id': 13, 'title': 'Bug fixes', 'owner_id': 7, 'owner': {'id': 7, 'name': 'Ada'}},
 ],
 'task_count': 1,
 'contributor_names': ['Ada']}
```

## Execution Order

```mermaid
flowchart LR
    a["resolve_tasks"] --> b["TaskView.resolve_owner"]
    b --> c["post_task_count"]
    c --> d["post_contributor_names"]
```

1.  All `resolve_*` methods run first — loading descendants recursively.
2.  `post_*` runs only after descendant data is ready.

This timing is why `post_*` is ideal for derived fields — counts, summaries, and other values computed from the resolved subtree.

## resolve_* vs post_*

| | `resolve_*` | `post_*` |
|---|---|---|
| Needs external IO? | Yes | Usually no |
| Runs before descendants ready? | Yes | No |
| Good for counts, sums, formatting? | Sometimes | Yes |
| Return value resolved again? | Yes | No |

## Common Patterns

Formatting:

```python
class TaskView(BaseModel):
    priority: int
    priority_label: str = ""

    def post_priority_label(self):
        return {1: "Low", 2: "Medium", 3: "High"}.get(self.priority, "Unknown")
```

Aggregation:

```python
class OrderView(BaseModel):
    items: list[OrderItem] = []
    total: float = 0.0

    def resolve_items(self, loader=Loader(item_loader)):
        return loader.load(self.id)

    def post_total(self):
        return sum(item.price * item.quantity for item in self.items)
```

Enrichment from nested data:

```python
class SprintView(BaseModel):
    tasks: list[TaskView] = []
    has_overdue: bool = False

    def resolve_tasks(self, loader=Loader(task_loader)):
        return loader.load(self.id)

    def post_has_overdue(self):
        return any(t.due_date < date.today() for t in self.tasks)
```

## post_* Parameters

### context

Access the global context dict passed to `Resolver`:

```python
def post_visible_task_count(self, context):
    user_role = context.get('role', 'viewer')
    if user_role == 'admin':
        return len(self.tasks)
    return len([t for t in self.tasks if t.visible])
```

### parent

Access the direct parent node — useful for tree structures:

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

Access data exposed by ancestors via `ExposeAs` (see [Cross-Layer Data Flow](./cross_layer_data_flow.md)):

```python
def post_full_title(self, ancestor_context):
    sprint_name = ancestor_context.get('sprint_name', '')
    return f"{sprint_name} / {self.title}"
```

### collector

Collect data from descendant nodes via `SendTo` (see [Cross-Layer Data Flow](./cross_layer_data_flow.md)):

```python
def post_contributors(self, collector=Collector('contributors')):
    return collector.values()
```

### loader

`post_*` can also use `Loader` — the same parameter as `resolve_*`. This is an escape hatch for loading supplemental data where the load key itself comes from a resolved field:

```python
def resolve_owner(self, loader=Loader(user_loader)):
    return loader.load(self.owner_id)

def post_department_name(self, loader=Loader(department_loader)):
    # owner.department_id is only available after resolve_owner
    if self.owner:
        return loader.load(self.owner.department_id)
```

Two caveats:

1.  Data loaded in `post_*` is **not resolved recursively** — nested `resolve_*` / `post_*` will not run.
2.  Other `post_*` methods on the same object cannot depend on it.

## post_default_handler

A special method that runs after all other `post_*` methods. It does not auto-assign — you set fields manually:

```python
def post_task_count(self):
    return len(self.tasks)

def post_default_handler(self):
    # runs after post_task_count
    self.summary = f"{self.task_count} tasks in this sprint"
```

## When to Stop Here

`resolve_*` + `post_*` covers the majority of data assembly needs. Most endpoints never need more than this.

## Next

- [Cross-Layer Data Flow](./cross_layer_data_flow.md) — share data between parent and child nodes without explicit traversal code.
- [ERD and AutoLoad](./erd_and_autoload.md) — centralize relationship declarations when they start repeating across models.
