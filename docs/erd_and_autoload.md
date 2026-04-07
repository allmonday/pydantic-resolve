# ERD and AutoLoad

[中文版](./erd_and_autoload.zh.md) | [docs](./index.md)

Manual `resolve_*` methods are the right entry point. But once the same relationships start repeating across multiple response models, the problem changes.

You are no longer asking “how do I load this field?” You are asking “where should the source of truth for this relationship live?”

That is the point where ERD mode becomes worth the upfront cost.

## The Duplication Signal

If your codebase starts to accumulate patterns like these, the relationships are probably ready to move into ERD:

- `TaskCard.resolve_owner`
- `TaskDetail.resolve_owner`
- `SprintBoard.resolve_tasks`
- `SprintReport.resolve_tasks`

The loader logic may still be correct, but the relationship knowledge is now duplicated.

## Cost vs Benefit

| Question | Manual Core API | ERD + `AutoLoad` |
|---|---|---|
| First endpoint | Faster | Slower |
| Upfront setup | Low | Medium |
| Reusing the same relation in many models | Repetitive | Centralized |
| Changing a relation later | Update many `resolve_*` methods | Update one declaration |
| GraphQL and MCP reuse | Separate work | Natural extension |

## The Same Scenario in ERD Mode

```python
from typing import Annotated, Optional

from pydantic import BaseModel
from pydantic_resolve import (
	DefineSubset,
	Relationship,
	base_entity,
	config_global_resolver,
)


BaseEntity = base_entity()


class UserEntity(BaseModel, BaseEntity):
	id: int
	name: str


class TaskEntity(BaseModel, BaseEntity):
	__relationships__ = [
		Relationship(fk='owner_id', name='owner', target=UserEntity, loader=user_loader)
	]
	id: int
	title: str
	owner_id: int


class SprintEntity(BaseModel, BaseEntity):
	__relationships__ = [
		Relationship(fk='id', name='tasks', target=list[TaskEntity], loader=task_loader)
	]
	id: int
	name: str


diagram = BaseEntity.get_diagram()
AutoLoad = diagram.create_auto_load()
config_global_resolver(diagram)


class TaskView(TaskEntity):
	owner: Annotated[Optional[UserEntity], AutoLoad()] = None


class SprintView(SprintEntity):
	tasks: Annotated[list[TaskView], AutoLoad()] = []
	task_count: int = 0

	def post_task_count(self):
		return len(self.tasks)
```

## What Changed

- `resolve_owner` disappeared from the view model.
- `resolve_tasks` disappeared from the view model.
- relationship declarations moved into `__relationships__`.
- `post_task_count` stayed exactly where it belongs.

That last point matters: ERD removes repeated relationship wiring, but it does not replace business-specific post-processing.

## Two Ways to Declare the ERD

The example above uses inline relationship declarations on the entity classes themselves:

```python
class TaskEntity(BaseModel, BaseEntity):
	__relationships__ = [
		Relationship(fk='owner_id', name='owner', target=UserEntity, loader=user_loader)
	]
```

That style works well when the entity class is already owned by the current application layer and you are comfortable attaching relationship metadata directly to it.

There is also a second style: declare the ERD externally with `ErDiagram` and `Entity`.

```python
from pydantic import BaseModel
from pydantic_resolve import Entity, ErDiagram, Relationship, config_global_resolver


class UserEntity(BaseModel):
	id: int
	name: str


class TaskEntity(BaseModel):
	id: int
	title: str
	owner_id: int


class SprintEntity(BaseModel):
	id: int
	name: str


diagram = ErDiagram(
	entities=[
		Entity(
			kls=TaskEntity,
			relationships=[
				Relationship(fk='owner_id', name='owner', target=UserEntity, loader=user_loader)
			],
		),
		Entity(
			kls=SprintEntity,
			relationships=[
				Relationship(fk='id', name='tasks', target=list[TaskEntity], loader=task_loader)
			],
		),
		Entity(kls=UserEntity, relationships=[]),
	],
)

AutoLoad = diagram.create_auto_load()
config_global_resolver(diagram)


class TaskView(TaskEntity):
	owner: Annotated[Optional[UserEntity], AutoLoad()] = None


class SprintView(SprintEntity):
	tasks: Annotated[list[TaskView], AutoLoad()] = []
```

### When External Declaration Is a Better Fit

External `ErDiagram(...)` declaration is often the better choice when:

- you do not want to modify the entity classes themselves
- the same entity classes are shared across multiple modules or services
- you want one centralized place to inspect all relationship definitions
- the source classes come from another package or a compatibility layer

In short:

- use `__relationships__` when relationship metadata belongs naturally on the entity type
- use external `ErDiagram(...)` when relationship metadata should stay separate from the type definition

## The `diagram` and `AutoLoad` Must Match

This setup is not just ceremony:

```python
diagram = BaseEntity.get_diagram()
AutoLoad = diagram.create_auto_load()
config_global_resolver(diagram)
```

`create_auto_load()` embeds diagram-specific relationship metadata into the annotation, so the resolver must be configured with the same `diagram`.

## Hiding Internal Fields with `DefineSubset`

When the response model should hide internal fields such as `owner_id`, you can build on the same ERD using `DefineSubset`:

```python
class TaskSummary(DefineSubset):
	__subset__ = (TaskEntity, ('id', 'title'))
	owner: Annotated[Optional[UserEntity], AutoLoad()] = None
```

This keeps the relationship declaration centralized while letting different responses expose different field subsets.

## When Not to Use ERD Yet

Stay with manual Core API when:

- you only have a few response models
- the relationship structure is still moving quickly
- the duplication cost is not real yet

ERD is valuable, but it is a scaling step, not a rite of passage.

## Next

Continue to [GraphQL and MCP](./graphql_and_mcp.md) to see how the same ERD can power external interfaces.