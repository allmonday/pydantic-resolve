# Quick Start

[中文版](./quick_start.zh.md) | [docs](./index.md)

This page solves one endpoint-level problem with the smallest useful amount of code: each task has an `owner_id`, but the response model should expose a full `owner` object.

If you only need to fix a few N+1 issues in a handful of endpoints, this page and the next one may already be enough.

## The Problem

Imagine a task list API that starts from data like this:

```python
raw_tasks = [
		{"id": 10, "title": "Design docs", "owner_id": 7},
		{"id": 11, "title": "Refine examples", "owner_id": 8},
]
```

The response contract you actually want is not just `owner_id`. You want:

```json
{
	"id": 10,
	"title": "Design docs",
	"owner": {
		"id": 7,
		"name": "Ada"
	}
}
```

The naive implementation is usually a loop that fetches one owner per task. That is exactly the kind of N+1 problem pydantic-resolve is built to remove.

## Install

```bash
pip install pydantic-resolve
```

If you later want MCP support as well:

```bash
pip install pydantic-resolve[mcp]
```

## The Smallest Useful Example

```python
from typing import Optional

from pydantic import BaseModel
from pydantic_resolve import Loader, Resolver, build_object


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


tasks = [TaskView.model_validate(task) for task in raw_tasks]
tasks = await Resolver().resolve(tasks)
```

## What Each Piece Does

- `owner` starts as `None` because the root task data does not include full owner objects.
- `resolve_owner` describes how to fetch that missing field.
- `Loader(user_loader)` declares a batched dependency instead of executing a query directly.
- `Resolver().resolve(tasks)` walks the model tree, finds `resolve_*` methods, and fills missing data.

## Why `build_object` Matters

`user_loader` receives a list of keys, not a single key. It must return results aligned with the incoming key order.

```python
return build_object(users, user_ids, lambda user: user.id)
```

That line turns an unordered collection like `users` into a result list aligned with `user_ids`.

## Why This Avoids N+1

Suppose the task list contains 100 tasks. The resolver does not call `user_loader` 100 times. Instead:

1. it collects all requested `owner_id` values
2. it calls `user_loader` once for the whole batch
3. it maps each loaded user back to the right `TaskView.owner`

That is the core value of the library in its smallest form.

## Mental Model

The most useful first mental model is this:

> `resolve_*` means: this field needs data from outside the current node.

Everything else in the library builds on that idea.

## When to Stop Here

Staying at this level is completely reasonable when:

- you only need to fix a few related-data fields
- your response models are still changing quickly
- you do not have repeated relationship wiring across many models yet

## Next

Continue to [Core API](./core_api.md) to extend the same pattern from one field to a nested tree: `Sprint -> Task -> User`.