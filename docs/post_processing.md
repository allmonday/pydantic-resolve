# Post Processing

[中文版](./post_processing.zh.md) | [docs](./index.md)

`resolve_*` loads missing data. `post_*` is for everything that should happen after the current subtree is already assembled.

This distinction matters. If the reader does not understand it early, `post_*` quickly starts to look like a second, mysterious loading hook. It is not.

## Extend the Same Sprint Example

Now that `Sprint -> Task -> User` can already be resolved, we can derive two fields from the finished subtree:

- `task_count`
- `contributor_names`

```python
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
```

## Execution Order

For one sprint, the lifecycle now looks like this:

```mermaid
flowchart LR
	a["resolve_tasks"] --> b["TaskView.resolve_owner"]
	b --> c["post_task_count"]
	c --> d["post_contributor_names"]
```

The exact implementation can be async under the hood, but the mental model is simple:

1. load descendants first
2. run `post_*` only after descendant data is ready

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

- counts and totals
- sorted display fields
- deduplicated labels
- string formatting based on already-loaded descendants
- business summaries that should not require another query

## What `post_*` Is Not For

Avoid using `post_*` as a hidden relationship loader. If a field needs external data, keep that behavior in `resolve_*`.

That separation keeps the code readable:

- `resolve_*` answers: where does the missing data come from?
- `post_*` answers: what do we do with the data after it is ready?

## A Useful Boundary

`post_*` can accept advanced parameters such as `context`, `parent`, `ancestor_context`, and `collector`. But those features are easier to understand after the basic timing model is already clear.

## Next

Continue to [Cross-Layer Data Flow](./cross_layer_data_flow.md) to see how ancestors and descendants can coordinate without explicit traversal code.