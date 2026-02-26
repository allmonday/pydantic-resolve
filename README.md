# Pydantic Resolve

> A tool for building Domain layer modeling and use case assembly.

[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![PyPI Downloads](https://static.pepy.tech/badge/pydantic-resolve/month)](https://pepy.tech/projects/pydantic-resolve)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)

[中文版](./README.zh.md)

## What is this?

**pydantic-resolve** is a Pydantic-based declarative data assembly tool that enables you to build complex data structures with concise code, without writing tedious data fetching and assembly logic.

It solves three core problems:

1. **Eliminate N+1 queries**: Built-in DataLoader automatically batches related data loading, no manual batch query management needed
2. **Clear layered architecture**: Entity-First design keeps business concepts independent of data storage, database changes no longer affect API contracts
3. **Elegant data composition**: Handle cross-layer data passing and aggregation effortlessly with declarative methods like `resolve`, `post`, `Expose`, `Collect`

## Installation

```bash
pip install pydantic-resolve
```

> Note: pydantic-resolve v2+ only supports Pydantic v2

**More resources**: [Full Documentation](https://allmonday.github.io/pydantic-resolve/) | [Example Project](https://github.com/allmonday/composition-oriented-development-pattern) | [Live Demo](https://www.fastapi-voyager.top/voyager/) | [API Reference](https://allmonday.github.io/pydantic-resolve/api/)

---

## 1. Basic Features - Resolve, Post, and DataLoader

### The Problem

In daily development, we often need to assemble complex data structures from multiple data sources. Consider a task management system where you need to return a team list containing Sprints, each Sprint containing Stories, each Story containing Tasks, and each Task needing owner information. The traditional approach traps you in a loop: query main data, collect related IDs, batch query related data, manually build mapping dictionaries, then loop to assemble results. This process is not only verbose and error-prone but also leads to the classic N+1 query problem—forgetting to batch load results in performance disasters.

Even when you carefully implement batch loading, this data assembly logic scatters across every corner of the project. Every API endpoint that needs related data has similar code, violating the DRY principle and making optimization difficult. Worse yet, this imperative data fetching approach mixes technical details of "how to fetch data" with business logic of "what data is needed," increasing cognitive load.

### pydantic-resolve's Declarative Solution

pydantic-resolve lets you describe data dependencies declaratively, and the framework automatically handles data fetching and assembly details. You just need to define "this task needs an owner," and the framework automatically collects all required owner IDs, batches queries, then populates results into the right places. This not only eliminates N+1 query risks but also makes code clearer and more maintainable.

The core of declarative data assembly is two methods: `resolve_` and `post_`. `resolve_` methods declare how to fetch related data, while `post_` methods perform post-processing and computation after all data loading completes. Combined with DataLoader's automatic batch loading, you can implement complex data assembly logic with concise code.

```python
from pydantic import BaseModel
from typing import Optional, List
from pydantic_resolve import Resolver, Loader, build_list

# Define batch data loader
async def user_batch_loader(user_ids: list[int]):
    async with get_db_session() as session:
        result = await session.execute(select(User).where(User.id.in_(user_ids)))
        users = result.scalars().all()
        return build_list(users, user_ids, lambda u: u.id)

# Define response models
class UserResponse(BaseModel):
    id: int
    name: str
    email: str

class TaskResponse(BaseModel):
    id: int
    name: str
    owner_id: int

    # Declare: fetch owner via owner_id
    owner: Optional[UserResponse] = None
    def resolve_owner(self, loader=Loader(user_batch_loader)):
        return loader.load(self.owner_id)

class SprintResponse(BaseModel):
    id: int
    name: str

    # Declare: fetch all tasks for this sprint via sprint_id
    tasks: List[TaskResponse] = []
    def resolve_tasks(self, loader=Loader(sprint_to_tasks_loader)):
        return loader.load(self.id)

    # Post-process: calculate total task count after tasks are loaded
    total_tasks: int = 0
    def post_total_tasks(self):
        return len(self.tasks)

# Use Resolver to resolve data
@app.get("/sprints", response_model=List[SprintResponse])
async def get_sprints():
    # 1. Fetch base data from database
    sprints_data = await get_sprints_from_db()

    # 2. Convert to Pydantic models
    sprints = [SprintResponse.model_validate(s) for s in sprints_data]

    # 3. Resolver automatically resolves all related data
    return await Resolver().resolve(sprints)
```

This simple example demonstrates the core power of pydantic-resolve. When you have multiple Sprints, each with multiple Tasks, and each Task needs to load an owner, the traditional approach requires nested loops and is prone to N+1 queries. With pydantic-resolve, you simply declare data dependencies, and the framework automatically collects all required IDs, merges them into batch queries, then correctly populates results into each object.

DataLoader's batch loading capability is the "hidden magic" behind it all. Suppose you have 3 Sprints, each with 10 Tasks, and these Tasks belong to 5 different users. The traditional approach might execute 1 Sprint query + 3 Task queries + 30 User queries (if you forget to batch). DataLoader automatically merges these requests into 1 Sprint query + 3 Task queries + 1 User query (via `WHERE id IN (...)`). This significantly reduces database round trips and eliminates the need to manually manage batch query complexity.

---

## 2. Complex Data Structures - Expose and Collector

### The Cross-Layer Data Passing Challenge

In real business scenarios, data often needs to flow bidirectionally between parent and child nodes. For example, a Story might need to pass its name to all child Tasks, so Tasks can display a full path like "StoryName - TaskName". Or conversely, a Story might need to collect all Task owners to generate a "related developers" list. In traditional code, this cross-layer data passing creates tight coupling—parents need to know children's requirements, children need to know parents' structure, and changes to either side can affect the other.

pydantic-resolve provides an elegant solution through `ExposeAs` and `Collector`. `ExposeAs` lets parent nodes expose data to descendant nodes without explicitly passing parameters. `Collector` lets parent nodes collect data from all child nodes without manually traversing and aggregating. These two mechanisms make data flow more natural and significantly reduce coupling between parent and child nodes.

### ExposeAs: Parent Nodes Expose Data to Child Nodes

`ExposeAs` lets you expose parent node fields to descendant nodes, which child nodes' `resolve_` or `post_` methods can access through `ancestor_context`. This is very useful for scenarios where parent context needs to be passed to child nodes.

```python
from pydantic_resolve import ExposeAs
from typing import Annotated

class StoryResponse(BaseModel):
    id: int
    # Expose name to child nodes, aliased as story_name
    name: Annotated[str, ExposeAs('story_name')]

    tasks: List[TaskResponse] = []

class TaskResponse(BaseModel):
    id: int
    name: str

    # post method can access data exposed by ancestor nodes
    full_name: str = ""
    def post_full_name(self, ancestor_context):
        # Get story_name exposed by parent (Story)
        story_name = ancestor_context.get('story_name')
        return f"{story_name} - {self.name}"
```

In this example, Story's name field is exposed as `story_name`, and all child Tasks can access this value in their `post_full_name` method. This eliminates the need to explicitly pass story_name when creating Tasks, reducing parameter passing complexity.

### Collector: Parent Nodes Collect Data from Child Nodes

`Collector` lets parent nodes collect data from all child nodes, commonly used to aggregate child node information. Combined with the `SendTo` annotation, specific fields of child nodes can be automatically sent to parent node collectors.

```python
from pydantic_resolve import Collector, SendTo
from typing import Annotated

class TaskResponse(BaseModel):
    id: int
    owner_id: int

    # Load owner and send to parent's related_users collector
    owner: Annotated[Optional[UserResponse], SendTo('related_users')] = None
    def resolve_owner(self, loader=Loader(user_batch_loader)):
        return loader.load(self.owner_id)

class StoryResponse(BaseModel):
    id: int
    name: str

    tasks: List[TaskResponse] = []
    def resolve_tasks(self, loader=Loader(story_to_tasks_loader)):
        return loader.load(self.id)

    # Collect all child node owners
    related_users: List[UserResponse] = []
    def post_related_users(self, collector=Collector(alias='related_users')):
        # collector.values() returns all deduplicated UserResponse objects
        return collector.values()
```

In this example, each Task's owner is automatically sent to the parent Story's `related_users` collector. Story's `post_related_users` method receives all deduplicated user lists. This is very useful for business scenarios like "show all related developers" and doesn't require manually writing traversal and deduplication logic.

---

## 3. Advanced Features - Application Layer Business Models (Entity-First)

### The ORM-First Architectural Dilemma

Most FastAPI projects follow a similar pattern: define SQLAlchemy ORM models first, then create Pydantic schemas based on these models. This "ORM-first, Pydantic-follows" pattern is so prevalent that few developers question its rationality. But when we deeply analyze its practical application, some deep problems emerge.

Pydantic schemas passively duplicate ORM model field definitions, causing type definitions to be repeated in two places. When the database adds new fields or modifies field types, you need to update both ORM models and Pydantic schemas, easily leading to omissions or inconsistencies. Even worse, business concepts become deeply polluted by database structure—APIs expose database foreign keys like `owner_id` and `reporter_id` instead of business roles like "owner" and "reporter." Frontend developers need to understand database design to use APIs, violating the Law of Demeter.

When data comes from multiple sources, this architecture's problems become even more obvious. User info might be in PostgreSQL, order data in MongoDB, inventory status fetched from RPC services, recommendation lists read from Redis cache. Lack of a unified abstraction layer makes the system difficult to adapt to data source changes—every migration or upgrade ripples through the entire codebase.

### Entity-First: Business Concepts as Architecture Core

The core idea of Entity-First architecture is: **domain models are the architecture's core, data layer is just an implementation detail**. Business entities (Entity) should express pure domain concepts like "user," "task," "project," not database tables. These entities define business object structures and their relationships, independent of any technical implementation. API contracts should be designed based on specific use cases, selecting required fields from domain models and adding use-case-specific computed fields and validation logic.

pydantic-resolve provides complete tool support for Entity-First architecture. Through ERD (Entity Relationship Diagram) for unified entity relationship management, DataLoader pattern for automatic data fetching optimization and N+1 query avoidance, and DefineSubset mechanism for type definition reuse and composition. More importantly, it provides an automatic data assembly execution layer—developers only need to declare "what data is needed" without caring about "how to fetch and assemble data."

```python
from pydantic_resolve import base_entity, Relationship, LoadBy, config_global_resolver, DefineSubset

# 1. Define business entities (not dependent on ORM)
BaseEntity = base_entity()

class UserEntity(BaseModel):
    """User entity: express business concepts"""
    id: int
    name: str
    email: str

class TaskEntity(BaseModel, BaseEntity):
    """Task entity: define business relationships"""
    __relationships__ = [
        Relationship(
            field='owner_id',
            target_kls=UserEntity,
            loader=user_batch_loader  # don't care where it loads from
        )
    ]
    id: int
    name: str
    owner_id: int
    estimate: int

class StoryEntity(BaseModel, BaseEntity):
    """Story entity"""
    __relationships__ = [
        Relationship(field='id', target_kls=list[TaskEntity], loader=story_to_tasks_loader)
    ]
    id: int
    name: str

# 2. Register ERD (centralized relationship management)
config_global_resolver(BaseEntity.get_diagram())

# 3. Define API Response from Entity (select fields + extend)
class UserSummary(DefineSubset):
    __subset__ = (UserEntity, ('id', 'name'))

class TaskResponse(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'name', 'estimate'))

    # LoadBy auto-resolves owner, no need to write resolve method
    owner: Annotated[Optional[UserSummary], LoadBy('owner_id')] = None

class StoryResponse(DefineSubset):
    __subset__ = (StoryEntity, ('id', 'name'))

    # LoadBy auto-resolves tasks
    tasks: Annotated[List[TaskResponse], LoadBy('id')] = []

# 4. Use (completely shield database details)
@app.get("/stories")
async def get_stories():
    # Fetch main data
    stories = await get_stories_from_db()

    # Convert and auto-resolve all related data
    stories = [StoryResponse.model_validate(s) for s in stories]
    return await Resolver().resolve(stories)
```

The introduction of `LoadBy` brings significant code simplification. In the traditional resolve pattern, you need to write `resolve_owner`, `resolve_tasks`, and other methods in each Response class—mostly repetitive boilerplate code: get loader, call load method, return result. With `LoadBy`, this logic completely disappears.

The simple `LoadBy('owner_id')` annotation automatically finds relationships defined in the ERD: `TaskEntity` has an `owner_id` field that connects to `UserEntity` via `user_batch_loader`. Resolver automatically uses this loader to fetch data—you don't need to write any resolve methods. This not only reduces code volume but also makes Response definitions clearer—you just declare "this field needs to load via owner_id" without caring about "how to load."

More importantly, when relationship definitions change, you only need to modify the `Relationship` configuration in the ERD, and all places using `LoadBy` automatically adapt. For example, replacing `user_batch_loader` with `user_from_rpc_loader` requires no changes to Response code. This centralized configuration management makes relationship maintenance exceptionally simple.

The core value of this layered architecture lies in **stability and evolvability**. When database structures need optimization (like splitting large tables, adjusting indexes), you only modify Loader implementations, while Entities and Responses remain completely unaffected. When business requirements change and API contracts need adjustment, you only modify Response definitions, while Entities and Loaders stay unchanged. When business logic evolves and requires new entity relationships, you only update ERD definitions, and existing data access logic remains stable.

---

## 4. Visualization - FastAPI Voyager Integration

### Why Visualization?

pydantic-resolve's declarative approach makes code concise, but it also brings a challenge: the logic of data flow becomes "invisible." When you see a `LoadBy('owner_id')` annotation, you know it will auto-resolve, but you might not be clear about the underlying loading chain, dependencies, and data flow direction. When debugging complex data structures, this invisibility increases understanding cost.

fastapi-voyager is a visualization tool designed specifically for pydantic-resolve that turns declarative data dependencies into visible, interactive charts. Like putting "X-ray glasses" on your code, you can see at a glance which fields are loaded via resolve, which are computed via post, which data is exposed from parents, and which is collected from children. Click any node to highlight its upstream dependencies and downstream consumers, making data flow crystal clear.

### Quick Start

```bash
pip install fastapi-voyager
```

```python
from fastapi import FastAPI
from fastapi_voyager import create_voyager

app = FastAPI()

# Mount voyager to visualize your API
app.mount('/voyager', create_voyager(
    app,
    enable_pydantic_resolve_meta=True,  # Show pydantic-resolve metadata
    er_diagram=BaseEntity.get_diagram()  # Show entity relationship diagram (optional)
))
```

Visit `http://localhost:8000/voyager` to see interactive visualization.

### Understanding the Visualization

When you enable `enable_pydantic_resolve_meta=True`, fastapi-voyager uses color-coded markers to display pydantic-resolve operations:

- 🟢 **resolve** - Field loaded via `resolve_{field}` method or `LoadBy`
- 🔵 **post** - Field computed via `post_{field}` method
- 🟣 **expose as** - Field exposed to descendant nodes via `ExposeAs`
- 🔴 **send to** - Field data sent to parent collectors via `SendTo`
- ⚫ **collectors** - Field collects data from child nodes via `Collector`

This color coding lets you quickly understand the direction and method of data flow. When you see a Task model's `owner` field marked with green resolve, you know it will auto-load via DataLoader. When you see a Story model's `related_users` field marked with black collectors, you know it will collect owner data from all child Tasks.

fastapi-voyager's interactive features make debugging much easier. Click any model to view its upstream dependencies (what data it needs) and downstream consumers (what depends on it). Double-click nodes to jump to source code definitions for quick location. Search functionality lets you quickly find specific models and trace their relationships. Combined with ERD view, you can also see entity-level definition relationships, understanding your system's data architecture from a higher level.

**Live Demo**: [https://www.fastapi-voyager.top/voyager/?tag=sample_1](https://www.fastapi-voyager.top/voyager/?tag=sample_1)

**Project**: [github.com/allmonday/fastapi-voyager](https://github.com/allmonday/fastapi-voyager)

---

## 5. GraphQL Support

pydantic-resolve now supports GraphQL query interface, leveraging the existing ERD system to automatically generate Schema and dynamically create Pydantic models based on GraphQL queries.

### Installation

```bash
# Install with GraphQL support
pip install "pydantic-resolve[graphql]"

# Or install graphql-core directly
pip install graphql-core
```

### Quick Start

```python
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Dict, Any
from pydantic_resolve import base_entity, query, config_global_resolver
from pydantic_resolve.graphql import GraphQLHandler, SchemaBuilder

app = FastAPI()

# 1. Define BaseEntity
BaseEntity = base_entity()

# 2. Define Entity with @query methods
class UserEntity(BaseModel, BaseEntity):
    id: int
    name: str
    email: str

    @query(name='users')
    async def get_all(cls, limit: int = 10) -> list['UserEntity']:
        return await fetch_users(limit=limit)

# 3. Configure global resolver
config_global_resolver(BaseEntity.get_diagram())

# 4. Create GraphQL handler
handler = GraphQLHandler(BaseEntity.get_diagram())

# 5. Define endpoint
@app.post("/graphql")
async def graphql_endpoint(req: Dict[str, Any]):
    return await handler.execute(query=req["query"])
```

### Query Example

```graphql
query {
  users(limit: 10) {
    id
    name
    email
  }
}
```

---

## 6. Why Not GraphQL?

Although pydantic-resolve is inspired by GraphQL, it's better suited as a BFF (Backend For Frontend) layer solution:

| Feature | GraphQL | pydantic-resolve |
|----------|---------|------------------|
| Performance | Requires complex DataLoader configuration | Built-in batch loading |
| Type Safety | Requires additional toolchain | Native Pydantic type support |
| Learning Curve | Steep (Schema, Resolver, Loader...) | Gentle (only need Pydantic) |
| Debugging | Difficult | Simple (standard Python code) |
| Integration | Requires additional server | Seamless integration with existing frameworks |
| Flexibility | Queries too flexible, hard to optimize | Explicit API contracts |

---

## License

MIT License

## Author

tangkikodo (allmonday@126.com)
