# Scenario Contract

[中文版](./scenario_contract.zh.md) | [docs](./index.md)

This file defines the canonical scenario for the `docs/` learning path. Every main-path page should reuse this model so the reader never has to remap concepts between pages.

## Domain Model

| Entity | Key Fields | Role in the Tutorial |
|---|---|---|
| `Sprint` | `id`, `name` | Root response node |
| `Task` | `id`, `title`, `sprint_id`, `owner_id` | Nested child node |
| `User` | `id`, `name` | Related data loaded into `Task.owner` |

## Canonical Relationships

- `Sprint.id -> Task.sprint_id`
- `Task.owner_id -> User.id`

## Canonical Response Fields

- `Sprint.tasks`
- `Task.owner`
- `Sprint.task_count`
- `Sprint.contributor_names`
- `Sprint.contributors`
- `Task.full_title`

## Canonical Loader Names

- `task_loader`
- `user_loader`

## Canonical Class Names

- Manual composition: `UserView`, `TaskView`, `SprintView`
- ERD mode: `UserEntity`, `TaskEntity`, `SprintEntity`

## Canonical Methods

- `SprintView.resolve_tasks`
- `TaskView.resolve_owner`
- `SprintView.post_task_count`
- `SprintView.post_contributor_names`
- `SprintView.post_contributors`
- `TaskView.post_full_title`

## Canonical Cross-Layer Names

- Expose alias: `sprint_name`
- Collector alias: `contributors`

## Canonical Seed Data

Use examples that can plausibly come from data sources like this:

```python
raw_sprints = [
	{"id": 1, "name": "Sprint 24"},
	{"id": 2, "name": "Sprint 25"},
]

raw_tasks = [
	{"id": 10, "title": "Design docs", "sprint_id": 1, "owner_id": 7},
	{"id": 11, "title": "Refine examples", "sprint_id": 1, "owner_id": 8},
]
```

The exact seed data can change, but the field names and relationships should not.

## Example Progression

Every page should extend the same example in this order:

1. Load `Task.owner`
2. Load `Sprint.tasks`
3. Compute `task_count` and `contributor_names`
4. Expose `sprint_name` downward and collect `contributors` upward
5. Replace repeated `resolve_*` wiring with `Relationship` and `AutoLoad`
6. Reuse the same ERD for GraphQL and MCP

## Terminology

- `Resolver` — the traversal orchestrator
- `Loader(...)` — dependency declaration inside `resolve_*` methods
- `DataLoader` — batching behavior or `aiodataloader`
- `ERD` — application-layer relationship declarations (not limited to database diagrams)

## Scope

The main path uses this scenario exclusively. Pages outside the main path (API reference, migration notes, changelog, motivation) may use different examples when the topic requires it.