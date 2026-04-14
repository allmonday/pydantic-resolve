# Reframing the Developer Experience of Data Assembly: pydantic-resolve vs SQLAlchemy ORM Query Patterns

## Background

What do backend engineers write most often? Usually it is pulling data from a database and assembling nested JSON for frontend APIs.

Take an agile project management API as an example. The frontend may want data like this:

```json
{
  "id": 1,
  "name": "Sprint 24",
  "stories": [
    {
      "id": 10,
      "title": "User login",
      "tasks": [
        {
          "id": 100,
          "title": "Design login page",
          "owner": { "id": 1, "name": "Ada" }
        }
      ]
    }
  ]
}
```

That is a four-level nesting chain: Sprint -> Story -> Task -> User. Not extremely deep, but deep enough to become painful.

SQLAlchemy ORM can absolutely do this with `relationship` and eager loading. But as nesting gets deeper and the same dataset must support more API variants, the `options(...)` chain grows longer and harder to maintain.

[pydantic-resolve](https://github.com/allmonday/pydantic-resolve) takes a different approach. It is built around Pydantic models and borrows GraphQL DataLoader-style batching. You declare what the data shape should look like, and the framework recursively traverses, batches queries, and assembles nested structures automatically. No hand-written options chains, no N+1 anxiety, and the schema itself becomes the single source of truth for loading behavior.

This article compares the two approaches through three progressive scenarios, letting the code speak for itself.

---

## The Foundation: Shared SQLAlchemy Models

First, an important point: pydantic-resolve is not trying to replace SQLAlchemy. Its loaders still execute SQLAlchemy queries. Both approaches share the same ORM models. The difference is how data gets assembled after it is fetched.

```python
# models.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(50))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    story_id: Mapped[int] = mapped_column(ForeignKey("stories.id"))

    owner: Mapped["User"] = relationship(lazy="raise")
    story: Mapped["Story"] = relationship(back_populates="tasks", lazy="raise")


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(50))
    sprint_id: Mapped[int] = mapped_column(ForeignKey("sprints.id"))

    tasks: Mapped[list["Task"]] = relationship(back_populates="story", lazy="raise")
    sprint: Mapped["Sprint"] = relationship(back_populates="stories", lazy="raise")


class Sprint(Base):
    __tablename__ = "sprints"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))

    stories: Mapped[list["Story"]] = relationship(back_populates="sprint", lazy="raise")
```

Notice every relationship uses `lazy="raise"`. Any accidental lazy load fails fast. That forces both approaches to explicitly declare what to load, which makes the comparison fair.

---

## Scenario 1: Full Hierarchical Loading

**Requirement**: A sprint list endpoint that returns every Sprint with all Stories, every Story with all Tasks, and every Task with its owner.

### SQLAlchemy ORM Approach

```python
from typing import Optional
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from models import Sprint, Story, Task


# ---- Pydantic schema (for ORM serialization) ----

class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class TaskSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    status: str
    owner_id: int
    owner: Optional[UserSchema] = None


class StorySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    status: str
    tasks: list[TaskSchema] = []


class SprintSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    stories: list[StorySchema] = []


# ---- Query ----

async def get_sprints_full_orm(session: AsyncSession) -> list[dict]:
    stmt = (
        select(Sprint)
        .options(
            selectinload(Sprint.stories)
            .selectinload(Story.tasks)
            .joinedload(Task.owner)
        )
        .order_by(Sprint.id)
    )

    result = await session.execute(stmt)
    sprints = result.scalars().unique().all()

    return [SprintSchema.model_validate(s).model_dump() for s in sprints]
```

Writing this requires juggling multiple concerns at once.

First, the options chain: four data levels require a three-step chain, `Sprint.stories -> Story.tasks -> Task.owner`. Miss one link, and `lazy="raise"` explodes when serialization touches unloaded relationships.

Second, at each level you must choose between `joinedload` (JOIN strategy) and `selectinload` (separate IN query strategy), which means understanding their SQL behavior. If you use `joinedload`, you must remember `.unique()` because JOINs can duplicate parent rows.

Most frustratingly, schema and options become implicitly coupled. If schema declares `stories: list[StorySchema]`, options must include `selectinload(Sprint.stories)`. Change one side and forget the other, and you find out only at runtime.

### pydantic-resolve Approach

```python
from typing import Optional
from pydantic import BaseModel, ConfigDict
from pydantic_resolve import Resolver, Loader, build_list, build_object
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from models import Sprint as SprintModel
from models import Story as StoryModel
from models import Task as TaskModel
from models import User as UserModel


# async_session: async_sessionmaker (initialized at app startup)


# ---- Loaders: define each relationship once and reuse globally ----

async def story_batch_loader(sprint_ids: list[int]):
    async with async_session() as session:
        stmt = select(StoryModel).where(StoryModel.sprint_id.in_(sprint_ids))
        rows = (await session.scalars(stmt)).all()
    return build_list(rows, sprint_ids, lambda s: s.sprint_id)


async def task_batch_loader(story_ids: list[int]):
    async with async_session() as session:
        stmt = select(TaskModel).where(TaskModel.story_id.in_(story_ids))
        rows = (await session.scalars(stmt)).all()
    return build_list(rows, story_ids, lambda t: t.story_id)


async def user_batch_loader(user_ids: list[int]):
    async with async_session() as session:
        stmt = select(UserModel).where(UserModel.id.in_(user_ids))
        rows = (await session.scalars(stmt)).all()
    return build_object(rows, user_ids, lambda u: u.id)


# ---- View schema: declare the data shape ----

class UserView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class TaskView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    status: str
    owner_id: int

    owner: Optional[UserView] = None
    def resolve_owner(self, loader=Loader(user_batch_loader)):
        return loader.load(self.owner_id)


class StoryView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    status: str

    tasks: list[TaskView] = []
    def resolve_tasks(self, loader=Loader(task_batch_loader)):
        return loader.load(self.id)


class SprintView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

    stories: list[StoryView] = []
    def resolve_stories(self, loader=Loader(story_batch_loader)):
        return loader.load(self.id)


# ---- Query entry ----

async def get_sprints_full_resolve() -> list[dict]:
    async with async_session() as session:
        stmt = select(SprintModel).order_by(SprintModel.id)
        rows = (await session.scalars(stmt)).all()

    sprints = [SprintView.model_validate(s) for s in rows]
    sprints = await Resolver().resolve(sprints)
    return [s.model_dump() for s in sprints]
```

With pydantic-resolve, the shape of the code changes significantly.

The entry query becomes a flat `select(Sprint)` with no options chain. Each relationship is declared by its own `resolve_*` method, and Resolver walks the tree recursively. More importantly, DataLoader merges same-type loads into batched `WHERE ... IN (...)` queries by default, so N+1 is handled automatically.

There is also a subtle but critical difference: in ORM style, schema and options are two independent definitions that must stay in sync manually. In pydantic-resolve, schema includes loading logic (`resolve_*`) directly. One definition, one maintenance point. Loaders are globally reusable too: write `story_batch_loader`, `task_batch_loader`, and `user_batch_loader` once, then reuse across endpoints.

### Scenario 1 Summary

| Dimension | SQLAlchemy ORM | pydantic-resolve |
|------|---------------|------------------|
| Entry query | `select(Sprint).options(...)` with a 3-level chain | Flat `select(Sprint)` |
| Loading strategy | Choose joinedload/selectinload per level | Each loader uses independent `WHERE IN` batching |
| Maintenance points | Schema + options chain must be synchronized | Schema alone contains loading declarations |
| N+1 safety | Depends on fully correct options | Automatic DataLoader batching |

---

## Scenario 2: Partial Loading (Lean Fields)

**Requirement**: A sprint list page that only needs each Story's `title` and `status`. Task-level data is not needed.

### SQLAlchemy ORM Approach

```python
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import selectinload, load_only, noload
from sqlalchemy.ext.asyncio import AsyncSession

from models import Sprint, Story


class StoryBriefSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    title: str
    status: str


class SprintBriefSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    stories: list[StoryBriefSchema] = []


async def get_sprints_brief_orm(session: AsyncSession) -> list[dict]:
    stmt = (
        select(Sprint)
        .options(
            selectinload(Sprint.stories)
            .load_only(Story.title, Story.status)
            .noload(Story.tasks)
        )
        .order_by(Sprint.id)
    )

    result = await session.execute(stmt)
    sprints = result.scalars().unique().all()

    return [SprintBriefSchema.model_validate(s).model_dump() for s in sprints]
```

Here you are managing two orthogonal concepts: `load_only(Story.title, Story.status)` controls **which columns to fetch**, while `noload(Story.tasks)` controls **which relationships to block**.

Strictly speaking, `model_validate` only touches fields declared in schema, so this example may still work without `noload`. But in real projects, `noload` is still good defensive practice. If someone later accesses `story.tasks` in the same session context (logging, middleware, debug `repr`, etc.), `lazy="raise"` will fail.

The cost is additional cognitive load: options must express both "what I want" (`load_only`) and "what I explicitly do not want" (`noload`). Every new view variant often means a new options chain plus a paired schema.

### pydantic-resolve Approach

```python
from pydantic import BaseModel, ConfigDict
from pydantic_resolve import Resolver, Loader
from sqlalchemy import select

from models import Sprint as SprintModel


class StoryBriefView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    title: str
    status: str
    # No resolve_tasks method means no Task loading.


class SprintBriefView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

    stories: list[StoryBriefView] = []
    def resolve_stories(self, loader=Loader(story_batch_loader)):
        return loader.load(self.id)


async def get_sprints_brief_resolve() -> list[dict]:
    async with async_session() as session:
        stmt = select(SprintModel).order_by(SprintModel.id)
        rows = (await session.scalars(stmt)).all()

    sprints = [SprintBriefView.model_validate(s) for s in rows]
    sprints = await Resolver().resolve(sprints)
    return [s.model_dump() for s in sprints]
```

If `resolve_tasks` is not declared, Task data is never loaded. This is a whitelist model, in clear contrast with ORM's blacklist-style `noload` blocks.

But there is a natural question: if `story_batch_loader` still uses `select(StoryModel)`, does it over-fetch fields when `StoryBriefView` only needs two?

That is where `_query_meta` helps. During DataLoader initialization, Resolver derives metadata from the target schema and stores it on loader `_query_meta`. A custom loader can use this metadata for query optimization:

```python
async def story_batch_loader(sprint_ids: list[int]):
    async with async_session() as session:
        stmt = select(StoryModel).where(StoryModel.sprint_id.in_(sprint_ids))

        # self._query_meta['fields'] is derived from schema declarations.
        # StoryBriefView declares title and status, so fields = ['title', 'status'].
        fields = getattr(story_batch_loader, '_query_meta', {}).get('fields')
        if fields:
            # Query only required columns plus the FK column.
            columns = [getattr(StoryModel, f) for f in fields] + [StoryModel.sprint_id]
            stmt = stmt.options(load_only(*columns))

        rows = (await session.scalars(stmt)).all()
    return build_list(rows, sprint_ids, lambda s: s.sprint_id)
```

For hand-written loaders, this optimization is manual. Later we will show `build_relationship`, where auto-generated loaders already include this behavior. Switch to a leaner schema, and the loader fetches fewer columns automatically.

This captures the core difference for partial loading: ORM requires **manual** `load_only` + `noload` composition in options chains; pydantic-resolve **derives** required columns and relationships from schema declarations. The schema becomes the single source of truth for query optimization.

### Scenario 2 Summary

| Dimension | SQLAlchemy ORM | pydantic-resolve |
|------|---------------|------------------|
| Lean fields | Manually specify `load_only(...)` | Schema fields derive `_query_meta`; loader fetches only needed columns |
| Relationship blocking | Explicit `noload(...)` | Omit `resolve_*` and nothing is loaded |
| Mental model | Blacklist: state what to load and what to block | Whitelist: schema declares exactly what is loaded |
| Cost of new variants | New options chain + new schema | New schema, reused loaders, automatic optimization |

---

## Scenario 3: Derived Field Computation

**Requirement**: A sprint detail endpoint needs two additional fields: `total_task_count` (all tasks across stories) and `contributor_names` (unique sorted task owner names). Neither field exists in the database.

### SQLAlchemy ORM Approach

```python
from typing import Optional
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from models import Sprint, Story, Task


# ---- Pydantic schema ----

class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class TaskSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    status: str
    owner_id: int
    owner: Optional[UserSchema] = None


class StorySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    status: str
    tasks: list[TaskSchema] = []


class SprintStatsSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    stories: list[StorySchema] = []
    total_task_count: int = 0
    contributor_names: list[str] = []


# ---- Query + manual derived computation ----

async def get_sprints_with_stats_orm(session: AsyncSession) -> list[dict]:
    # Derived fields require full loading.
    stmt = (
        select(Sprint)
        .options(
            selectinload(Sprint.stories)
            .selectinload(Story.tasks)
            .joinedload(Task.owner)
        )
        .order_by(Sprint.id)
    )

    result = await session.execute(stmt)
    sprints = result.scalars().unique().all()

    output = []
    for sprint in sprints:
        schema = SprintStatsSchema.model_validate(sprint)

        # Derived fields are computed with manual traversal.
        total = 0
        contributors: set[str] = set()
        for story in schema.stories:
            for task in story.tasks:
                total += 1
                if task.owner:
                    contributors.add(task.owner.name)

        schema.total_task_count = total
        schema.contributor_names = sorted(contributors)
        output.append(schema.model_dump())

    return output
```

At this point, the pain becomes obvious.

Even if you only need two aggregate values, options are still almost identical to Scenario 1, because you must load all tasks before counting. `model_validate` handles nested serialization, but there is no lifecycle hook for derived fields, so you manually compute and assign them in a loop.

It gets worse when reused. If another endpoint also needs `total_task_count`, you either copy/paste logic or extract a helper manually. Every new derived field makes the function larger: `overdue_count`, `avg_tasks_per_story`, and so on.

### pydantic-resolve Approach

```python
from pydantic import BaseModel, ConfigDict
from pydantic_resolve import Resolver, Loader


class SprintDetailView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

    stories: list[StoryView] = []  # Reuse StoryView from Scenario 1.
    def resolve_stories(self, loader=Loader(story_batch_loader)):
        return loader.load(self.id)

    # ---- Derived fields ----

    total_task_count: int = 0
    def post_total_task_count(self):
        return sum(len(story.tasks) for story in self.stories)

    contributor_names: list[str] = []
    def post_contributor_names(self):
        names: set[str] = set()
        for story in self.stories:
            for task in story.tasks:
                if task.owner:
                    names.add(task.owner.name)
        return sorted(names)


async def get_sprints_with_stats_resolve() -> list[dict]:
    async with async_session() as session:
        stmt = select(SprintModel).order_by(SprintModel.id)
        rows = (await session.scalars(stmt)).all()

    sprints = [SprintDetailView.model_validate(s) for s in rows]
    sprints = await Resolver().resolve(sprints)
    return [s.model_dump() for s in sprints]
```

The key capability here is `post_*`. The framework guarantees this order: **all `resolve_*` methods (including descendants) complete before any `post_*` method runs**.

So when `post_total_task_count` runs, `self.stories` is already populated, and each story already has tasks with owner data. You no longer need to manually coordinate loading completion.

Adding another derived field is straightforward: write another `post_*` method. Each method is self-contained and can be unit-tested by constructing a Pydantic object directly.

### Scenario 3 Summary

| Dimension | SQLAlchemy ORM | pydantic-resolve |
|------|---------------|------------------|
| Derived logic location | Mixed into query function, manual assignment | `post_*` methods colocated with field definitions |
| Execution ordering | Developer must ensure load-before-compute | Framework guarantees resolve-before-post |
| Adding derived fields | Inflate one function with more loops | Add independent `post_*` methods |
| Reusability | Usually requires helper extraction | Reuse with schema inheritance/composition |
| Testability | Requires mocking full ORM query chains | Test `post_*` directly with Pydantic objects |

---

## Going Further: Remove Hand-Written Loaders with ER Diagram

In the three scenarios above, pydantic-resolve loaders are globally reusable, but still hand-written. `story_batch_loader`, `task_batch_loader`, and `user_batch_loader` all repeat the same pattern: `select ... where ... in_`. It is natural to ask whether loaders can be generated from SQLAlchemy relationship metadata directly.

Yes. pydantic-resolve provides `build_relationship`, which inspects SQLAlchemy relationship definitions and auto-generates DataLoaders for each relationship type (many-to-one, one-to-many, many-to-many), removing boilerplate.

```python
from typing import Annotated, Optional
from pydantic import BaseModel, ConfigDict
from pydantic_resolve import Resolver, config_global_resolver, ErDiagram, DefineSubset
from pydantic_resolve.integration.sqlalchemy import build_relationship
from pydantic_resolve.integration.mapping import Mapping
from sqlalchemy import select

from models import Sprint as SprintModel, Story as StoryModel, Task as TaskModel, User as UserModel


# ---- Step 1: Define DTOs aligned with ORM base fields ----

class UserDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

class TaskDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    status: str
    owner_id: int
    story_id: int

class StoryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    status: str
    sprint_id: int

class SprintDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


# ---- Step 2: Auto-generate relationships and loaders from ORM metadata ----

entities = build_relationship(
    mappings=[
        Mapping(entity=UserDTO,   orm=UserModel),
        Mapping(entity=TaskDTO,   orm=TaskModel),
        Mapping(entity=StoryDTO,  orm=StoryModel),
        Mapping(entity=SprintDTO, orm=SprintModel),
    ],
    session_factory=lambda: async_session(),
)

diagram = ErDiagram(entities=[]).add_relationship(entities)
AutoLoad = diagram.create_auto_load()
config_global_resolver(diagram)


# ---- Step 3: Replace resolve_* methods with AutoLoad annotations ----

class UserView(UserDTO):
    pass

class TaskView(TaskDTO):
    owner: Annotated[Optional[UserDTO], AutoLoad()] = None

class StoryView(StoryDTO):
    tasks: Annotated[list[TaskView], AutoLoad()] = []

class SprintView(SprintDTO):
    stories: Annotated[list[StoryView], AutoLoad()] = []


# ---- Query entry: same as before ----

async def get_sprints_full() -> list[dict]:
    async with async_session() as session:
        stmt = select(SprintModel).order_by(SprintModel.id)
        rows = (await session.scalars(stmt)).all()

    sprints = [SprintView.model_validate(s) for s in rows]
    sprints = await Resolver().resolve(sprints)
    return [s.model_dump() for s in sprints]
```

Compared with the hand-written version, `story_batch_loader`, `task_batch_loader`, and `user_batch_loader` disappear, and each schema no longer needs explicit `resolve_*` methods. `build_relationship` reads FK relationships from ORM metadata and generates batched loaders. `AutoLoad()` tells Resolver to load that field via ER relationships.

The mental model becomes: **define relationships in ORM -> define fields in DTO -> connect with `AutoLoad` -> let Resolver orchestrate**. Relationship definitions stay in one place.

### Use DefineSubset to Trim Response Fields

One detail to note: in the example above, `TaskView` inherits all fields from `TaskDTO`, including foreign keys like `owner_id` and `story_id`. These are internal implementation details and usually should not appear in API responses.

Manually overriding each field is awkward. pydantic-resolve provides `DefineSubset` to select exposed fields while preserving ER metadata needed by `AutoLoad`:

```python
from pydantic_resolve import DefineSubset


# Expose only id, title, status. owner_id and story_id are hidden automatically.
class TaskView(DefineSubset):
    __subset__ = (TaskDTO, ['id', 'title', 'status'])
    owner: Annotated[Optional[UserDTO], AutoLoad()] = None


# Expose only id, title, status. sprint_id is hidden automatically.
class StoryView(DefineSubset):
    __subset__ = (StoryDTO, ['id', 'title', 'status'])
    tasks: Annotated[list[TaskView], AutoLoad()] = []


class SprintView(SprintDTO):
    stories: Annotated[list[StoryView], AutoLoad()] = []

    total_task_count: int = 0
    def post_total_task_count(self):
        return sum(len(story.tasks) for story in self.stories)
```

`DefineSubset` does two things: `(TaskDTO, ['id', 'title', 'status'])` limits exposed fields, while FK fields required by `AutoLoad` are auto-injected and marked `exclude=True`. They remain available internally for loading, but do not appear in `model_dump()`.

That gives you a clean API response:

```json
{
  "id": 1, "name": "Sprint 24",
  "total_task_count": 2,
  "stories": [
    {
      "id": 10, "title": "User login", "status": "in_progress",
      "tasks": [
        { "id": 100, "title": "Design login page", "status": "todo",
          "owner": { "id": 1, "name": "Ada" } }
      ]
    }
  ]
}
```

No leaked `owner_id`, `story_id`, or `sprint_id`. DTOs stay complete for internal use, and `DefineSubset` trims API-facing views.

`post_*` derived logic is still hand-written by design. `AutoLoad` solves relationship traversal, not business computation. But removing hand-written loaders, removing `resolve_*` boilerplate, and avoiding manual field trimming already cuts a large amount of repetitive code in larger domains.

---

## Final Comparison

| Dimension | SQLAlchemy ORM Eager Loading | pydantic-resolve |
|------|------------------------------|------------------|
| **Full loading** | Options chain must match nesting depth exactly | Per-level declarations, auto-orchestrated by Resolver |
| **Partial loading** | `load_only` + `noload` composition | Reuse same loaders across different schemas |
| **Derived fields** | Manual traversal and assignment | `post_*` methods with guaranteed execution order |
| **Cost of new variants** | New options chain + new schema (~25 lines) | New schema (~15 lines), loader reuse |
| **N+1 safety** | Depends on complete and correct options | Automatic DataLoader batching |
| **Mental model** | Configure queries to match output | Declare output shape and let framework fill it |
| **Maintenance points** | Keep schema and options in sync | Schema holds loading and post-processing behavior |

## Closing Thoughts

These two approaches are **not mutually exclusive**. pydantic-resolve loaders still run SQLAlchemy queries and share the same ORM models. You can adopt it incrementally in an existing ORM codebase: start with the endpoints that have the deepest nesting and the most variants.

The core difference is a difference in thinking. With ORM eager loading, the question is: "How do I configure queries to construct this shape?" That is query-first. With pydantic-resolve, the question is: "What shape should this API return?" That is contract-first.

For simple cases such as two levels and one endpoint, ORM eager loading is often enough. But once you reach 3-4 levels and need multiple variants (list view, detail view, analytics view) over the same data, pydantic-resolve's loader reuse and schema composition advantages compound quickly.
