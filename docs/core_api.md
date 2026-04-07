# Core API

[中文版](./core_api.zh.md) | [docs](./index.md)

The quick start showed one field loaded from outside the current node. This page extends the same idea into a nested response tree.

The goal is still manual composition. No ERD yet. No `AutoLoad` yet. Just plain `resolve_*` methods, batched loaders, and recursive traversal.

## From One Field to One Tree

We now want a sprint response that looks like this:

- `Sprint` has many `tasks`
- each `Task` has one `owner`

That gives us a nested tree: `Sprint -> Task -> User`.

## Full Example

```python
from typing import List, Optional

from pydantic import BaseModel
from pydantic_resolve import Loader, Resolver, build_list, build_object


class UserView(BaseModel):
	id: int
	name: str


async def user_loader(user_ids: list[int]):
	users = await db.query(User).filter(User.id.in_(user_ids)).all()
	return build_object(users, user_ids, lambda user: user.id)


class TaskView(BaseModel):
	id: int
	title: str
	owner_id: int
	owner: Optional[UserView] = None

	def resolve_owner(self, loader=Loader(user_loader)):
		return loader.load(self.owner_id)


async def task_loader(sprint_ids: list[int]):
	tasks = await db.query(Task).filter(Task.sprint_id.in_(sprint_ids)).all()
	return build_list(tasks, sprint_ids, lambda task: task.sprint_id)


class SprintView(BaseModel):
	id: int
	name: str
	tasks: List[TaskView] = []

	def resolve_tasks(self, loader=Loader(task_loader)):
		return loader.load(self.id)


sprints = [SprintView.model_validate(sprint) for sprint in raw_sprints]
sprints = await Resolver().resolve(sprints)
```

## Why `build_list` Exists

`user_loader` uses `build_object(...)` because one user id maps to one user.

`task_loader` uses `build_list(...)` because one sprint id maps to many tasks.

```python
return build_list(tasks, sprint_ids, lambda task: task.sprint_id)
```

That line groups the returned tasks by `sprint_id` and aligns the grouped result with the incoming `sprint_ids` order.

## What the Resolver Does Recursively

The important thing to notice is that you do not write any manual traversal code. No nested loops. No orchestration layer that says “load tasks, then for every task load owner”.

The resolver handles that sequence for you:

1. load `SprintView.tasks`
2. inspect each returned `TaskView`
3. load `TaskView.owner`
4. continue until there are no more unresolved fields

That recursive walk is why the Core API scales better than endpoint-specific glue code.

## When Manual `resolve_*` Is Still the Right Tool

Manual Core API is often enough when:

- you only have a few response models
- relationship wiring is not repeating yet
- you want each endpoint to stay maximally explicit
- the shape of the response is still changing quickly

At this stage, explicitness is a feature, not a limitation.

## What This Page Does Not Add Yet

This page intentionally stops before derived fields. Right now we only load related data. We are not yet computing fields such as:

- `task_count`
- `contributor_names`

Those belong to the next concept layer.

## Next

Continue to [Post Processing](./post_processing.md) to see when a field should be computed after the subtree is already assembled.