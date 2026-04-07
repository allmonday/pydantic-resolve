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

## Terminology Rules

- Use `Resolver` for the traversal orchestrator.
- Use `Loader(...)` for dependency declaration inside `resolve_*` methods.
- Use `DataLoader` only when referring to batching behavior or `aiodataloader`.
- Use `ERD` to mean application-layer relationship declarations, not only database diagrams.
- In Chinese pages, keep code identifiers in English and translate only the surrounding explanation.

## Content Rules

- Do not switch to unrelated examples such as `Company/Department/Employee` in the main path.
- Do not introduce GraphQL before ERD is already established.
- Do not present `post_*` as another data-loading hook.
- Do not introduce `ExposeAs` or `Collector` before the reader already understands `resolve_*` and `post_*`.

## Allowed Exceptions

Breaking this contract is acceptable only when the page is explicitly outside the main path, for example:

- API reference pages
- migration notes
- changelog entries
- historical or motivational essays

If a page breaks the scenario contract, it should say so explicitly.