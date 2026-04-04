# Pydantic Resolve

> Declarative data assembly for Pydantic — eliminate N+1 queries with minimal code.

[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![PyPI Downloads](https://static.pepy.tech/badge/pydantic-resolve/month)](https://pepy.tech/projects/pydantic-resolve)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)

[中文版](./README.zh.md)

![](./docs/images/features.png)

---

**pydantic-resolve** is inspired by GraphQL. It builds database-independent application-layer Entity Relationship Diagrams using DataLoader, providing rich data assembly and post-processing capabilities. It can also auto-generate GraphQL queries and MCP services.

## Why pydantic-resolve?

**Core capabilities:**

| Feature | What it does |
|---------|--------------|
| **Automatic Batching** | DataLoader eliminates N+1 queries automatically |
| **Declarative Assembly** | Declare dependencies, framework handles the rest |
| **ER Diagram + AutoLoad** | Define entity relationships, auto-resolve related data |
| **GraphQL Support** | Generate schema from ERD, query with dynamic models |
| **MCP Integration** | Expose GraphQL APIs to AI agents with progressive disclosure |

**One line to fetch nested data:**

```python
class Task(BaseModel):
    owner_id: int
    owner: Optional[User] = None

    def resolve_owner(self, loader=Loader(user_loader)):
        return loader.load(self.owner_id)  # That's it!

# Resolver automatically batches all owner lookups into one query
result = await Resolver().resolve(tasks)
```

---

## Quick Start

### Install

```bash
pip install pydantic-resolve
pip install pydantic-resolve[mcp]  # with MCP support
```

### The N+1 Problem

```python
# Traditional: 1 + N queries
for task in tasks:
    task.owner = await get_user(task.owner_id)  # N queries!
```

### The pydantic-resolve Solution

```python
from pydantic import BaseModel
from typing import Optional, List
from pydantic_resolve import Resolver, Loader, build_list

# 1. Define your loaders (batch queries)
async def user_loader(ids: list[int]):
    users = await db.query(User).filter(User.id.in_(ids)).all()
    return build_list(users, ids, lambda u: u.id)

async def task_loader(sprint_ids: list[int]):
    tasks = await db.query(Task).filter(Task.sprint_id.in_(sprint_ids)).all()
    return build_list(tasks, sprint_ids, lambda t: t.sprint_id)

# 2. Define your schema with resolve methods
class TaskResponse(BaseModel):
    id: int
    name: str
    owner_id: int

    owner: Optional[dict] = None
    def resolve_owner(self, loader=Loader(user_loader)):
        return loader.load(self.owner_id)

class SprintResponse(BaseModel):
    id: int
    name: str

    tasks: List[TaskResponse] = []
    def resolve_tasks(self, loader=Loader(task_loader)):
        return loader.load(self.id)

# 3. Resolve - framework handles batching automatically
@app.get("/sprints")
async def get_sprints():
    sprints = await get_sprint_data()
    return await Resolver().resolve([SprintResponse.model_validate(s) for s in sprints])
```

**Result:** 1 query per loader, regardless of data depth.

---

## Core Concepts

### Resolve: Declarative Data Loading

Instead of imperative data fetching, declare what you need:

```python
class Task(BaseModel):
    owner_id: int
    owner: Optional[User] = None

    def resolve_owner(self, loader=Loader(user_loader)):
        return loader.load(self.owner_id)
```

The framework:
1. Collects all `owner_id` values
2. Batches them into one query
3. Maps results back to correct objects

### DataLoader: Automatic Batching

DataLoader batches multiple requests within the same event loop tick:

```python
# Without DataLoader: 100 tasks = 100 user queries
# With DataLoader: 100 tasks = 1 user query (WHERE id IN (...))

async def user_loader(user_ids: list[int]):
    return await db.query(User).filter(User.id.in_(user_ids)).all()
```

### Post: Post-Processing After Resolution

After all `resolve_*` methods complete, use `post_*` methods to transform or aggregate data:

```python
class SprintResponse(BaseModel):
    tasks: List[TaskResponse] = []
    task_count: int = 0

    def post_task_count(self):
        return len(self.tasks)
```

`post_*` methods run after all nested data is fully resolved, making them ideal for:
- Computing derived values (counts, sums, averages)
- Formatting or cleaning up loaded data
- Aggregating results from child collections

```python
class OrderResponse(BaseModel):
    items: List[ItemResponse] = []
    total_price: Decimal = Decimal('0')

    def post_total_price(self):
        return sum(item.price for item in self.items)
```

`post_*` methods also accept parameters for context access (see Expose & Collect below).

### Expose & Collect: Cross-layer Data Flow

In nested data structures, parent and child nodes often need to share data. Traditional approaches require explicit parameter passing or tight coupling. pydantic-resolve provides two declarative mechanisms:

- **ExposeAs**: Parent nodes expose data to all descendants (downward flow)
- **SendTo + Collector**: Child nodes send data to parent collectors (upward flow)

This creates a clean separation — parent doesn't need to know child's structure, and child doesn't need explicit parent references.

```python
from pydantic_resolve import ExposeAs, Collector, SendTo
from typing import Annotated

# 1. Parent EXPOSES data to descendants (downward flow)
class Story(BaseModel):
    name: Annotated[str, ExposeAs('story_name')]
    tasks: List[Task] = []

# 2. Child ACCESSES ancestor context (no explicit parent reference needed)
class Task(BaseModel):
    def post_full_path(self, ancestor_context):
        return f"{ancestor_context['story_name']} / {self.name}"

# 3. Child SENDS data to parent collector (upward flow)
class Task(BaseModel):
    owner: Annotated[User, SendTo('contributors')] = None

class Story(BaseModel):
    contributors: List[User] = []
    def post_contributors(self, collector=Collector('contributors')):
        return collector.values()  # Auto-deduplicated list of all task owners
```

**Use cases:**
- Pass configuration/context down to nested objects (e.g., user permissions, locale)
- Aggregate results up from nested objects (e.g., collect all unique tags from posts)

---

## Declarative Mode: ER Diagram + AutoLoad

Quick Start and Core Concepts demonstrate pydantic-resolve's **Core API**: writing `resolve_*` methods and manually specifying Loaders. For simple use cases, this is sufficient.

When a project involves multiple interrelated entities, pydantic-resolve offers a **Declarative API**: define entity relationships and default loaders in an ER Diagram, then use `AutoLoad` to auto-generate the corresponding resolve methods.

Declarative API is built on top of Core API. `AutoLoad` fields generate equivalent `resolve_*` methods at runtime, so both modes can be freely mixed — you can still use `post_*` methods in Declarative Mode, or fall back to hand-written `resolve_*` for specific fields.

| | Core API | Declarative API |
|--|----------|-----------------|
| **Approach** | Hand-write `resolve_*` + specify `Loader` | Define ER Diagram + `AutoLoad` |
| **Control** | Full control | Convention over configuration |
| **Best for** | Simple projects, one-off data loading | Multiple related entities, GraphQL/MCP needed |
| **Relationships** | Scattered across Response classes | Centralized in ER Diagram |

### Define Entities and Relationships

Create a base class with `base_entity()`, then define relationships in `__relationships__`:

```python
from pydantic import BaseModel
from typing import Annotated, Optional
from pydantic_resolve import base_entity, Relationship, config_global_resolver

BaseEntity = base_entity()

class UserEntity(BaseModel, BaseEntity):
    id: int
    name: str

class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        # Loader can query Postgres, call RPC, or fetch from Redis
        # API consumers don't need to know where data comes from
        Relationship(fk='owner_id', target=UserEntity, name='owner', loader=user_loader)
    ]
    id: int
    name: str
    owner_id: int  # Internal FK, can be hidden from API

diagram = BaseEntity.get_diagram()
AutoLoad = diagram.create_auto_load()
config_global_resolver(diagram)
```

You can also use external declaration (`ErDiagram` + `Entity`) to separate relationship definitions from entity classes.

### Use AutoLoad

After defining the ER Diagram, annotate fields with `AutoLoad()` in Response models:

```python
from pydantic_resolve import DefineSubset

class TaskResponse(TaskEntity):
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
    # AutoLoad generates resolve_owner based on TaskEntity's __relationships__

# Usage is identical to Core API
result = await Resolver().resolve(tasks)
```

Use `DefineSubset` to selectively expose fields and hide internal FKs:

```python
class TaskResponse(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'name'))  # owner_id excluded
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
```

### Auto-Discover Relationships from ORM

Instead of manually defining `__relationships__`, use `build_relationship` to auto-discover ORM relationships and generate DataLoaders. Supports **SQLAlchemy**, **Django**, and **Tortoise ORM**.

```python
from pydantic_resolve import ErDiagram, config_resolver
from pydantic_resolve.contrib.sqlalchemy import build_relationship  # or .django / .tortoise
from pydantic_resolve.contrib.mapping import Mapping

# 1. Map DTOs to ORM models
entities = build_relationship(
    mappings=[
        Mapping(entity=StudentDTO, orm=StudentOrm),
        Mapping(entity=SchoolDTO, orm=SchoolOrm),
        Mapping(entity=CourseDTO, orm=CourseOrm),
    ],
    session_factory=session_factory,  # SQLAlchemy / Django / Tortoise
)

# 2. Add to ErDiagram
diagram = ErDiagram(entities=[]).add_relationship(entities)
AutoLoad = diagram.create_auto_load()
MyResolver = config_resolver("MyResolver", er_diagram=diagram)

# 3. Use AutoLoad — relationships are resolved automatically
class StudentView(StudentDTO):
    school: Annotated[SchoolDTO | None, AutoLoad()] = None
    courses: Annotated[list[CourseDTO], AutoLoad()] = []
```

`build_relationship` inspects ORM metadata and generates loaders for **Many-to-One**, **One-to-Many**, **Many-to-Many**, and **One-to-One** relationships. You can also apply filters:

```python
entities = build_relationship(
    mappings=[
        Mapping(entity=StudentDTO, orm=StudentOrm),
        Mapping(entity=SchoolDTO, orm=SchoolOrm, filters=[]),  # bypass default filter
        Mapping(entity=CourseDTO, orm=CourseOrm, filters=[CourseOrm.active.is_(True)]),
    ],
    session_factory=session_factory,
    default_filter=lambda cls: [cls.deleted.is_(False)],  # global default
)
```

### When to Use Declarative Mode

**Declarative Mode is a good fit when:**
- The project has 3+ interrelated entities
- You need to generate GraphQL schema or MCP services
- The team needs centralized relationship management
- You want to hide FK fields from API contracts

**Core API is sufficient when:**
- Only a few data loading requirements
- Simple data source
- No GraphQL or MCP needed

[→ Full ERD-Driven Guide](https://allmonday.github.io/pydantic-resolve/erd_driven/)

## Integrations

### GraphQL

Generate GraphQL schema from ERD and execute queries:

```python
from pydantic_resolve.graphql import GraphQLHandler

handler = GraphQLHandler(diagram)
result = await handler.execute("{ users { id name posts { title } } }")
```

[→ GraphQL Documentation](./demo/graphql/README.md)

### MCP

Expose GraphQL APIs to AI agents (requires `pip install pydantic-resolve[mcp]`):

```python
from pydantic_resolve import AppConfig, create_mcp_server

mcp = create_mcp_server(apps=[AppConfig(name="blog", er_diagram=diagram)])
mcp.run()
```

[→ MCP Documentation](https://allmonday.github.io/pydantic-resolve/api/)

### Visualization

Interactive ERD exploration with [fastapi-voyager](https://github.com/allmonday/fastapi-voyager):

```python
from fastapi_voyager import create_voyager

app.mount('/voyager', create_voyager(app, er_diagram=diagram))
```

---

## pydantic-resolve vs GraphQL

| Feature | GraphQL | pydantic-resolve |
|---------|---------|------------------|
| **N+1 Prevention** | Manual DataLoader setup | Built-in automatic batching |
| **Type Safety** | Separate schema files | Native Pydantic types |
| **Learning Curve** | Steep (Schema, Resolvers, Loaders) | Gentle (just Pydantic) |
| **Debugging** | Complex introspection | Standard Python debugging |
| **Integration** | Requires dedicated server | Works with any framework |
| **Query Flexibility** | Any client can query anything | Explicit API contracts |

---

## Resources

- 📖 [Full Documentation](https://allmonday.github.io/pydantic-resolve/)
- 🚀 [Example Project](https://github.com/allmonday/composition-oriented-development-pattern)
- 🎮 [Live Demo](https://www.fastapi-voyager.top/voyager/)
- 🎮 [Live Demo - GraphQL](https://www.fastapi-voyager.top/graphql)
- 📚 [API Reference](https://allmonday.github.io/pydantic-resolve/api/)

---

## License

MIT License

## Author

tangkikodo (allmonday@126.com)
