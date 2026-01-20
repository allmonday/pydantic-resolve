# Pydantic Resolve


> Transform Pydantic from a static data container into a powerful composable component

[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![PyPI Downloads](https://static.pepy.tech/badge/pydantic-resolve/month)](https://pepy.tech/projects/pydantic-resolve)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)

[中文版](./README.zh.md)

## What is this?

**pydantic-resolve** is a Pydantic-based data construction tool that enables you to assemble complex data structures **declaratively** without writing boring imperative glue code.

### What problem does it solve?

Consider this scenario: you need to provide API data to frontend clients from multiple data sources (databases, RPC services, etc.) that requires composition, transformation, and computation. How would you typically approach this?

```python
# Traditional approach: imperative data assembly
async def get_teams_with_detail(session):
    # 1. Fetch team list
    teams = await session.execute(select(Team))
    teams = teams.scalars().all()

    # 2. Fetch sprint list for each team
    for team in teams:
        team.sprints = await get_sprints_by_team(session, team.id)

        # 3. Fetch task list for each sprint
        for sprint in team.sprints:
            sprint.tasks = await get_tasks_by_sprint(session, sprint.id)

            # 4. Fetch owner information for each task
            for task in sprint.tasks:
                task.owner = await get_user_by_id(session, task.owner_id)

    # 5. Calculate some statistics
    for team in teams:
        team.total_tasks = sum(len(sprint.tasks) for sprint in team.sprints)

    return teams
```

**Problems**:
- Extensive nested loops
- N+1 query problem (poor performance)
- Difficult to maintain and extend
- Data fetching logic mixed with business logic

**The pydantic-resolve approach**:

```python
# Declarative: describe what you want, not how to do it
class TaskResponse(BaseModel):
    id: int
    name: str
    owner_id: int

    owner: Optional[UserResponse] = None
    def resolve_owner(self, loader=Loader(user_batch_loader)):
        return loader.load(self.owner_id)

class SprintResponse(BaseModel):
    id: int
    name: str

    tasks: list[TaskResponse] = []
    def resolve_tasks(self, loader=Loader(sprint_to_tasks_loader)):
        return loader.load(self.id)

class TeamResponse(BaseModel):
    id: int
    name: str

    sprints: list[SprintResponse] = []
    def resolve_sprints(self, loader=Loader(team_to_sprints_loader)):
        return loader.load(self.id)

    # Calculate statistics automatically after sprints are loaded
    total_tasks: int = 0
    def post_total_tasks(self):
        return sum(len(sprint.tasks) for sprint in self.sprints)

# Usage
teams = await query_teams_from_db(session)
result = await Resolver().resolve(teams)
```

**Advantages**:
- Automatic batch loading (using DataLoader pattern)
- No N+1 query problem
- Clear separation of data fetching logic
- Easy to extend and maintain

### Core Features

- **Declarative data composition**: Declare how to fetch related data via `resolve_{field}` methods
- **Automatic batch loading**: Built-in DataLoader automatically batches queries to avoid N+1 issues
- **Data post-processing**: Transform and compute data after fetching via `post_{field}` methods
- **Cross-layer data passing**: Parent nodes can expose data to descendants, children can collect data to parents
- **Entity Relationship Diagram (ERD)**: Define entity relationships and auto-generate resolution logic
- **Framework integration**: Seamless integration with FastAPI, Litestar, Django Ninja

## Quick Start

### Installation

```bash
pip install pydantic-resolve
```

> Note: pydantic-resolve v2+ only supports Pydantic v2

### Step 1: Define Data Loaders

First, you need to define batch data loaders (this is the Python implementation of Facebook's DataLoader pattern):

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic_resolve import build_list

# Batch fetch users
async def batch_get_users(session: AsyncSession, user_ids: list[int]):
    result = await session.execute(select(User).where(User.id.in_(user_ids)))
    return result.scalars().all()

# User loader
async def user_batch_loader(user_ids: list[int]):
    async with get_db_session() as session:
        users = await batch_get_users(session, user_ids)
        # Map user list to corresponding IDs
        return build_list(users, user_ids, lambda u: u.id)

# Batch fetch team tasks
async def batch_get_tasks_by_team(session: AsyncSession, team_ids: list[int]):
    result = await session.execute(select(Task).where(Task.team_id.in_(team_ids)))
    return result.scalars().all()

# Team task loader
async def team_to_tasks_loader(team_ids: list[int]):
    async with get_db_session() as session:
        tasks = await batch_get_tasks_by_team(session, team_ids)
        return build_list(tasks, team_ids, lambda t: t.team_id)
```

### Step 2: Define Response Models

Use Pydantic BaseModel to define response structures and declare how to fetch related data via `resolve_` prefixed methods:

```python
from typing import Optional, List
from pydantic import BaseModel
from pydantic_resolve import Resolver, Loader

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

class TaskResponse(BaseModel):
    id: int
    name: str
    owner_id: int

    # Declaration: fetch owner via owner_id
    owner: Optional[UserResponse] = None
    def resolve_owner(self, loader=Loader(user_batch_loader)):
        return loader.load(self.owner_id)

class TeamResponse(BaseModel):
    id: int
    name: str

    # Declaration: fetch all tasks for this team via team_id
    tasks: List[TaskResponse] = []
    def resolve_tasks(self, loader=Loader(team_to_tasks_loader)):
        return loader.load(self.id)
```

### Step 3: Use Resolver to Resolve Data

```python
from fastapi import FastAPI, Depends

app = FastAPI()

@app.get("/teams", response_model=List[TeamResponse])
async def get_teams():
    # 1. Fetch base data from database (multiple teams)
    teams_data = await get_teams_from_db()

    # 2. Convert to Pydantic models
    teams = [TeamResponse.model_validate(t) for t in teams_data]

    # 3. Resolve all related data
    result = await Resolver().resolve(teams)

    return result
```

That's it! Resolver will automatically:
1. Discover all `resolve_` methods
2. **Collect all task IDs needed by teams** (e.g., 3 teams require 3 task fetches)
3. **Batch call the corresponding loader** (one query to load all tasks instead of 3)
4. Populate results to corresponding fields

**The power of DataLoader**:
```python
# Assume 3 teams, each with multiple tasks
# Traditional approach: 3 queries
SELECT * FROM tasks WHERE team_id = 1
SELECT * FROM tasks WHERE team_id = 2
SELECT * FROM tasks WHERE team_id = 3

# DataLoader approach: 1 query
SELECT * FROM tasks WHERE team_id IN (1, 2, 3)
```

## Core Concepts Deep Dive

### DataLoader: The Secret Weapon for Batch Loading

**Problem**: Traditional related data loading leads to N+1 queries

```python
# Wrong example: N+1 queries
for task in tasks:
    task.owner = await get_user_by_id(task.owner_id)  # Generates N queries
```

**Solution**: DataLoader batch loading

```python
# DataLoader automatically batches requests
tasks = [Task1(owner_id=1), Task2(owner_id=2), Task3(owner_id=1)]

# DataLoader will merge these requests into one query:
# SELECT * FROM users WHERE id IN (1, 2)
```

### resolve Methods: Declare Data Dependencies

`resolve_{field_name}` methods are used to declare how to fetch data for that field:

```python
class CommentResponse(BaseModel):
    id: int
    content: str
    author_id: int

    # Resolver will automatically call this method and assign the return value to author field
    author: Optional[UserResponse] = None
    def resolve_author(self, loader=Loader(user_batch_loader)):
        return loader.load(self.author_id)
```

### post Methods: Data Post-Processing

After all `resolve_` methods complete execution, `post_{field_name}` methods are called. This can be used for:

- Computing derived fields
- Formatting data
- Aggregating child node data

```python
class SprintResponse(BaseModel):
    id: int
    name: str

    tasks: List[TaskResponse] = []
    def resolve_tasks(self, loader=Loader(sprint_to_tasks_loader)):
        return loader.load(self.id)

    # After tasks are loaded, calculate total task count
    total_tasks: int = 0
    def post_total_tasks(self):
        return len(self.tasks)

    # Calculate sum of all task estimates
    total_estimate: int = 0
    def post_total_estimate(self):
        return sum(task.estimate for task in self.tasks)
```

### Cross-Layer Data Passing

**Scenario**: Child nodes need to access parent node data, or parent nodes need to collect child node data

#### Expose: Parent Nodes Expose Data to Child Nodes

```python
from pydantic_resolve import ExposeAs

class StoryResponse(BaseModel):
    id: int
    name: Annotated[str, ExposeAs('story_name')]  # Expose to child nodes

    tasks: List[TaskResponse] = []

class TaskResponse(BaseModel):
    id: int
    name: str

    # Both post/resolve methods can access data exposed by ancestor nodes
    full_name: str = ""
    def post_full_name(self, ancestor_context):
        # Get parent (Story) name
        story_name = ancestor_context.get('story_name')
        return f"{story_name} - {self.name}"
```

#### Collect: Child Nodes Send Data to Parent Nodes

```python
from pydantic_resolve import Collector, SendTo

class TaskResponse(BaseModel):
    id: int
    owner_id: int

    # Load owner data and send to parent's related_users collector
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
        return collector.values()
```

## Advanced Usage

### Using Entity Relationship Diagram (ERD)

For complex applications, you can define entity relationships at the application level and automatically generate resolution logic:

```python
from pydantic_resolve import base_entity, Relationship, LoadBy, config_global_resolver

# 1. Define base entities
BaseEntity = base_entity()

class Story(BaseModel, BaseEntity):
    __relationships__ = [
        # Define relationship: load all tasks for this story via id field
        Relationship(field='id', target_kls=list['Task'], loader=story_to_tasks_loader),
        # Define relationship: load owner via owner_id field
        Relationship(field='owner_id', target_kls='User', loader=user_batch_loader),
    ]

    id: int
    name: str
    owner_id: int
    sprint_id: int

class Task(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(field='owner_id', target_kls='User', loader=user_batch_loader),
    ]

    id: int
    name: str
    owner_id: int
    story_id: int
    estimate: int

class User(BaseModel):
    id: int
    name: str
    email: str

# 2. Generate ER diagram and register to global Resolver
diagram = BaseEntity.get_diagram()
config_global_resolver(diagram)

# 3. When defining response models, no need to write resolve methods
class TaskResponse(BaseModel):
    id: int
    name: str
    owner_id: int

    # LoadBy automatically finds relationship definitions in ERD
    owner: Annotated[Optional[User], LoadBy('owner_id')] = None

class StoryResponse(BaseModel):
    id: int
    name: str

    tasks: Annotated[List[TaskResponse], LoadBy('id')] = []
    owner: Annotated[Optional[User], LoadBy('owner_id')] = None

# 4. Use directly
stories = await query_stories_from_db(session)
result = await Resolver().resolve(stories)
```

Advantages:
- Centralized relationship definition management
- More concise response models
- Type-safe
- Visualizable dependencies (with fastapi-voyager)

### Defining Data Subsets

If you only want to return a subset of entity fields, you can use `DefineSubset`:

```python
from pydantic_resolve import DefineSubset

# Assume you have a complete User model
class FullUser(BaseModel):
    id: int
    name: str
    email: str
    password_hash: str
    created_at: datetime
    updated_at: datetime

# Select only required fields
class UserSummary(DefineSubset):
    __subset__ = (FullUser, ('id', 'name', 'email'))

# Auto-generates:
# class UserSummary(BaseModel):
#     id: int
#     name: str
#     email: str
```

### Advanced Subset Configuration: SubsetConfig

For more complex configurations (like exposing fields to child nodes simultaneously), use `SubsetConfig`:

```python
from pydantic_resolve import DefineSubset, SubsetConfig

class StoryResponse(DefineSubset):
    __subset__ = SubsetConfig(
        kls=StoryEntity,              # Source model
        fields=['id', 'name', 'owner_id'],  # Fields to include
        expose_as=[('name', 'story_name')],  # Alias exposed to child nodes
        send_to=[('id', 'story_id_collector')]  # Send to collector
    )

# Equivalent to:
# class StoryResponse(BaseModel):
#     id: Annotated[int, SendTo('story_id_collector')]
#     name: Annotated[str, ExposeAs('story_name')]
#     owner_id: int
#
```

## Performance Optimization Tips

### Database Session Management

When using FastAPI + SQLAlchemy, pay attention to session lifecycle:

```python
@router.get("/teams", response_model=List[TeamResponse])
async def get_teams(session: AsyncSession = Depends(get_session)):
    # 1. Fetch base data (multiple teams)
    teams = await get_teams_from_db(session)

    # 2. Release session immediately (avoid deadlock)
    await session.close()

    # 3. Loaders inside Resolver will create new sessions
    teams = [TeamResponse.model_validate(t) for t in teams]
    result = await Resolver().resolve(teams)

    return result
```

### Batch Loading Optimization

Ensure your loader correctly implements batch loading:

```python
# Correct: batch load with IN query
async def user_batch_loader(user_ids: list[int]):
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users = result.scalars().all()
        return build_list(users, user_ids, lambda u: u.id)
```

**Advanced: Optimize Query Fields with `_query_meta`**

DataLoader can access required field information via `self._query_meta` to query only necessary data:

```python
from aiodataloader import DataLoader

class UserLoader(DataLoader):
    async def batch_load_fn(self, user_ids: list[int]):
        # Get fields required by response model
        required_fields = self._query_meta.get('fields', ['*'])

        # Query only required fields (optimize SQL query)
        async with get_session() as session:
            # If fields specified, query only those fields
            if required_fields != ['*']:
                columns = [getattr(User, f) for f in required_fields]
                result = await session.execute(
                    select(*columns).where(User.id.in_(user_ids))
                )
            else:
                result = await session.execute(
                    select(User).where(User.id.in_(user_ids))
                )

            users = result.scalars().all()
            return build_list(users, user_ids, lambda u: u.id)
```

**Advantages**:
- If `UserResponse` only needs `id` and `name`, SQL queries only these two fields
- Reduce data transfer and memory usage
- Improve query performance, especially for tables with many fields

**Note**: `self._query_meta` is populated after Resolver's first scan.

## Real-World Example

### Scenario: Project Management System

Requirements: Fetch all Sprints for a team, including:
- All Stories for each Sprint
- All Tasks for each Story
- Owner for each Task
- Statistics for each layer (total tasks, total estimates, etc.)

```python
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from pydantic_resolve import (
    Resolver, Loader, LoadBy,
    ExposeAs, Collector, SendTo,
    base_entity, Relationship, config_global_resolver,
    build_list, DefineSubset, SubsetConfig
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# 0. Define data loaders
async def user_batch_loader(user_ids: list[int]):
    """Batch load users"""
    async with get_db_session() as session:
        result = await session.execute(select(User).where(User.id.in_(user_ids)))
        users = result.scalars().all()
        return build_list(users, user_ids, lambda u: u.id)

async def story_to_tasks_loader(story_ids: list[int]):
    """Batch load Tasks for Stories"""
    async with get_db_session() as session:
        result = await session.execute(select(Task).where(Task.story_id.in_(story_ids)))
        tasks = result.scalars().all()
        return build_list(tasks, story_ids, lambda t: t.story_id)

async def sprint_to_stories_loader(sprint_ids: list[int]):
    """Batch load Stories for Sprints"""
    async with get_db_session() as session:
        result = await session.execute(select(Story).where(Story.sprint_id.in_(sprint_ids)))
        stories = result.scalars().all()
        return build_list(stories, sprint_ids, lambda s: s.sprint_id)

# 1. Define entities and ERD
BaseEntity = base_entity()

class UserEntity(BaseModel):
    """User entity"""
    id: int
    name: str
    email: str

class TaskEntity(BaseModel, BaseEntity):
    """Task entity"""
    __relationships__ = [
        Relationship(field='owner_id', target_kls=UserEntity, loader=user_batch_loader)
    ]
    id: int
    name: str
    owner_id: int
    story_id: int
    estimate: int

class StoryEntity(BaseModel, BaseEntity):
    """Story entity"""
    __relationships__ = [
        Relationship(field='id', target_kls=list[TaskEntity], loader=story_to_tasks_loader),
        Relationship(field='owner_id', target_kls=UserEntity, loader=user_batch_loader)
    ]
    id: int
    name: str
    owner_id: int
    sprint_id: int

class SprintEntity(BaseModel, BaseEntity):
    """Sprint entity"""
    __relationships__ = [
        Relationship(field='id', target_kls=list[StoryEntity], loader=sprint_to_stories_loader)
    ]
    id: int
    name: str
    team_id: int

# Register ERD
config_global_resolver(BaseEntity.get_diagram())

# 2. Define response models (use DefineSubset to select fields from entities)

# Base user response
class UserResponse(DefineSubset):
    __subset__ = (UserEntity, ('id', 'name'))

# Scenario 1: Basic data composition - Use LoadBy to auto-resolve related data
class TaskResponse(DefineSubset):
    __subset__ = SubsetConfig(
        kls=TaskEntity,
        fields=['id', 'name', 'estimate', 'owner_id']
    )

    # LoadBy auto-resolves owner based on Relationship definition in ERD
    owner: Annotated[Optional[UserResponse], LoadBy('owner_id')] = None

# Scenario 2: Parent exposes data to child nodes - Task names need Story prefix
class TaskResponseWithPrefix(DefineSubset):
    __subset__ = SubsetConfig(
        kls=TaskEntity,
        fields=['id', 'name', 'estimate', 'owner_id']
    )

    owner: Annotated[Optional[UserResponse], LoadBy('owner_id')] = None

    # post method can access data exposed by ancestor nodes
    full_name: str = ""
    def post_full_name(self, ancestor_context):
        # Get story_name exposed by parent (Story)
        story_name = ancestor_context.get('story_name')
        return f"{story_name} - {self.name}"

# Scenario 3: Compute extra fields - Story needs to calculate total estimate of all Tasks
class StoryResponse(DefineSubset):
    __subset__ = SubsetConfig(
        kls=StoryEntity,
        fields=['id', 'name', 'owner_id'],
        expose_as=[('name', 'story_name')]  # Expose to child nodes (used by Scenario 2)
    )

    # LoadBy auto-resolves tasks based on Relationship definition in ERD
    tasks: Annotated[List[TaskResponse], LoadBy('id')] = []

    # post_ method executes after all resolve_ methods complete
    total_estimate: int = 0
    def post_total_estimate(self):
        return sum(t.estimate for t in self.tasks)

# Scenario 4: Parent collects data from child nodes - Story needs to collect all involved developers
class TaskResponseForCollect(DefineSubset):
    __subset__ = SubsetConfig(
        kls=TaskEntity,
        fields=['id', 'name', 'estimate', 'owner_id'],
    )

    owner: Annotated[Optional[UserResponse], LoadBy('owner_id'), SendTo('related_users')] = None

class StoryResponseWithCollect(DefineSubset):
    __subset__ = (StoryEntity, ('id', 'name', 'owner_id'))

    tasks: Annotated[List[TaskResponseForCollect], LoadBy('id')] = []

    # Collect all child node owners
    related_users: List[UserResponse] = []
    def post_related_users(self, collector=Collector(alias='related_users')):
        return collector.values()

# Sprint response model - Combines all above features
class SprintResponse(DefineSubset):
    __subset__ = (SprintEntity, ('id', 'name'))

    # Use LoadBy to auto-resolve stories
    stories: Annotated[List[StoryResponse], LoadBy('id')] = []

    # Calculate statistics (total estimate of all stories)
    total_estimate: int = 0
    def post_total_estimate(self):
        return sum(s.total_estimate for s in self.stories)

# 3. API endpoint
@app.get("/sprints", response_model=List[SprintResponse])
async def get_sprints(session: AsyncSession = Depends(get_session)):
    """Fetch all Sprints with complete hierarchical data"""
    sprints_data = await get_sprints_from_db(session)
    await session.close()

    sprints = [SprintResponse.model_validate(s) for s in sprints_data]
    result = await Resolver().resolve(sprints)

    return result
```

**Architectural Advantages**:
- **Entity-Response Separation**: Entities define business entities and relationships, Responses define API return structures
- **Reusable Relationship Definitions**: Define relationships once via ERD, all response models can use `LoadBy` for auto-resolution
- **Type Safety**: DefineSubset ensures field types are inherited from entities
- **Flexible Composition**: Define different response models based on the same entities and reuse DataLoader
- **Query Optimization**: DataLoader can access required field info via `self._query_meta` to query only necessary data (e.g., SQL `SELECT` only required columns)

**Scenario Coverage**:
- **Scenario 1**: Basic data composition - Auto-resolve related data
- **Scenario 2**: Expose - Parent nodes expose data to child nodes (e.g., Task uses Story's name)
- **Scenario 3**: post - Compute extra fields (e.g., calculate total estimates)
- **Scenario 4**: Collect - Parent nodes collect data from child nodes (e.g., collect all developers)

Each scenario is independent and reusable, can be combined as needed.

## Visualizing Dependencies with fastapi-voyager

**pydantic-resolve** works best with [fastapi-voyager](https://github.com/allmonday/fastapi-voyager) - a powerful visualization tool that makes complex data relationships easy to understand.

### Why fastapi-voyager?

pydantic-resolve's declarative approach hides execution details, which can make it hard to understand **what's happening under the hood**. fastapi-voyager solves this by:

- **Color-coded operations**: See `resolve`, `post`, `expose`, and `collect` at a glance
- **Interactive exploration**: Click nodes to highlight upstream/downstream dependencies
- **ERD visualization**: View entity relationships defined in your data models
- **Source code navigation**: Double-click any node to jump to its definition
- **Quick search**: Find models and trace their relationships instantly

### Installation

```bash
pip install fastapi-voyager
```

### Basic Setup

```python
from fastapi import FastAPI
from fastapi_voyager import create_voyager

app = FastAPI()

# Mount voyager to visualize your API
app.mount('/voyager', create_voyager(
    app,
    enable_pydantic_resolve_meta=True  # Show pydantic-resolve metadata
))
```

Visit `http://localhost:8000/voyager` to see the interactive visualization!

### Understanding the Visualization

When you enable `enable_pydantic_resolve_meta=True`, fastapi-voyager uses color-coded markers to show pydantic-resolve operations:

#### Field Markers

- **● resolve** - Field data is loaded via `resolve_{field}` method or `LoadBy`
- **● post** - Field is computed via `post_{field}` method after all resolves complete
- **● expose as** - Field is exposed to descendant nodes via `ExposeAs`
- **● send to** - Field data is sent to parent collectors via `SendTo`
- **● collectors** - Field collects data from child nodes via `Collector`

#### Example

```python
class TaskResponse(BaseModel):
    id: int
    name: str
    owner_id: int

    # resolve: loaded via DataLoader
    owner: Annotated[Optional[UserResponse], LoadBy('owner_id')] = None

    # send to: owner data sent to parent's collector
    owner: Annotated[Optional[UserResponse], LoadBy('owner_id'), SendTo('related_users')] = None

class StoryResponse(BaseModel):
    id: int

    # expose as: name exposed to descendants
    name: Annotated[str, ExposeAs('story_name')]

    # resolve: tasks loaded via DataLoader
    tasks: Annotated[List[TaskResponse], LoadBy('id')] = []

    # post: computed from tasks
    total_estimate: int = 0
    def post_total_estimate(self):
        return sum(t.estimate for t in self.tasks)

    # collectors: collects from child nodes
    related_users: List[UserResponse] = []
    def post_related_users(self, collector=Collector(alias='related_users')):
        return collector.values()
```

**In fastapi-voyager**, you'll see:
- `owner` field marked with resolve and send to
- `name` field marked with expose as: story_name
- `tasks` field marked with resolve
- `total_estimate` field marked with post
- `related_users` field marked with collectors: related_users

### Visualizing Entity Relationships (ERD)

If you're using ERD to define entity relationships, fastapi-voyager can visualize them:

```python
from pydantic_resolve import base_entity, Relationship, config_global_resolver

# Define entities with relationships
BaseEntity = base_entity()

class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(field='owner_id', target_kls=UserEntity, loader=user_batch_loader)
    ]
    id: int
    name: str
    owner_id: int

class StoryEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(field='id', target_kls=list[TaskEntity], loader=story_to_tasks_loader)
    ]
    id: int
    name: str

# Register ERD
diagram = BaseEntity.get_diagram()
config_global_resolver(diagram)

# Visualize it in voyager
app.mount('/voyager', create_voyager(
    app,
    er_diagram=diagram,  # Show entity relationships
    enable_pydantic_resolve_meta=True
))
```

### Interactive Features

#### Click to Highlight
Click any model or route to see:
- **Upstream**: What this model depends on
- **Downstream**: What depends on this model

#### Double-Click to View Code
Double-click any node to:
- View the source code (if configured)
- Open the file in VSCode (by default)

#### Quick Search
- Press `Shift + Click` on a node to search for it
- Use the search box to find models by name
- See related models highlighted automatically

### Pro Tips

1. **Start Simple**: Begin with `enable_pydantic_resolve_meta=False` to see the basic structure
2. **Enable Metadata**: Turn on `enable_pydantic_resolve_meta=True` to see data flow
3. **Use ERD View**: Toggle ERD view to understand entity-level relationships
4. **Trace Data Flow**: Click a node and follow the colored links to understand data dependencies

### Live Demo

Check out the [live demo](https://www.newsyeah.fun/voyager/?tag=sample_1) to see fastapi-voyager in action!

### Learn More

- [fastapi-voyager Documentation](https://github.com/allmonday/fastapi-voyager)
- [Example Project](https://github.com/allmonday/composition-oriented-development-pattern)

---

**Key Insight**: fastapi-voyager turns pydantic-resolve's "hidden magic" into **visible, understandable data flows**, making it much easier to debug, optimize, and explain your code to others!

## Why Not GraphQL?

Although pydantic-resolve is inspired by GraphQL, it's better suited as a BFF (Backend For Frontend) layer solution:

| Feature | GraphQL | pydantic-resolve |
|----------|---------|------------------|
| Performance | Requires complex DataLoader configuration | Built-in batch loading |
| Type Safety | Requires additional toolchain | Native Pydantic type support |
| Learning Curve | Steep (Schema, Resolver, Loader...) | Gentle (only need Pydantic) |
| Debugging | Difficult | Simple (standard Python code) |
| Integration | Requires additional server | Seamless integration with existing frameworks |
| Flexibility | Queries too flexible, hard to optimize | Explicit API contracts |

## More Resources

- **Full Documentation**: https://allmonday.github.io/pydantic-resolve/
- **Example Project**: https://github.com/allmonday/composition-oriented-development-pattern
- **Live Demo**: https://www.newsyeah.fun/voyager/?tag=sample_1
- **API Reference**: https://allmonday.github.io/pydantic-resolve/api/

## Development

```bash
# Clone repository
git clone https://github.com/allmonday/pydantic_resolve.git
cd pydantic_resolve

# Install development dependencies
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Run tests
uv run pytest tests/

# View test coverage
tox -e coverage
```

## License

MIT License

## Author

tangkikodo (allmonday@126.com)

