[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![PyPI Downloads](https://static.pepy.tech/badge/pydantic-resolve/month)](https://pepy.tech/projects/pydantic-resolve)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)

Pydantic-resolve is a framework for composing complex data structures with an intuitive, declarative, resolver-based way, and then let the data easy to understand and adjust.

It provides three major functions to facilitate the acquisition and modification of multi-layered data.

- pluggable resolve methods and post methods, they can define how to fetch and modify nodes.
- transporting field data from ancestor nodes to their descendant nodes, through multiple layers.
- collecting data from any descendants nodes to their ancestor nodes, through multiple layers.

It supports:

- pydantic v1
- pydantic v2
- dataclass `from pydantic.dataclasses import dataclass`

If you have experience with GraphQL, this article provides comprehensive insights: [Resolver Pattern: A Better Alternative to GraphQL in BFF.](https://github.com/allmonday/resolver-vs-graphql/blob/master/README-en.md)

It could be seamlessly integrated with modern Python web frameworks including FastAPI, Litestar, and Django-ninja.

## Hello world

This snippet shows the basic capability of fetching descendant nodes in a declarative way, the specific query details are encapsulated inside the dataloader.

```python
from pydantic_resolve import Resolver
from biz_models import BaseTask, BaseStory, BaseUser
from biz_services import UserLoader, StoryTaskLoader

class Task(BaseTask):
    user: Optional[BaseUser] = None
    def resolve_user(self, loader=Loader(UserLoader)):
        return loader.load(self.assignee_id) if self.assignee_id else None

class Story(BaseStory):
    tasks: list[Task] = []
    def resolve_tasks(self, loader=Loader(StoryTaskLoader)):
        # this loader returns BaseTask,
        # Task inhert from BaseTask so that it can be initialized from it, then fetch the user.
        return loader.load(self.id)

stories = [Story(**s) for s in await query_stories()]
data = await Resolver().resolve(stories)
```

then it will transform flat stories into complicated stories with rich details:

BaseStory

```json
[
  { "id": 1, "name": "story - 1" },
  { "id": 2, "name": "story - 2" }
]
```

Story

```json
[
  {
    "id": 1,
    "name": "story - 1",
    "tasks": [
      {
        "id": 1,
        "name": "design",
        "user": {
          "id": 1,
          "name": "tangkikodo"
        }
      }
    ]
  },
  {
    "id": 2,
    "name": "story - 2",
    "tasks": [
      {
        "id": 2,
        "name": "add ut",
        "user": {
          "id": 2,
          "name": "john"
        }
      }
    ]
  }
]
```

## Installation

```
pip install pydantic-resolve
```

Starting from pydantic-resolve v1.11.0, both pydantic v1 and v2 are supported.

## Documentation

- **Documentation**: https://allmonday.github.io/pydantic-resolve/
- **Demo**: https://github.com/allmonday/pydantic-resolve-demo
- **Composition-Oriented Pattern**: https://github.com/allmonday/composition-oriented-development-pattern

## Quick Start

Building complex data structures requires only 3 systematic steps， let's take Agile's Story for example.

### 1. Define Domain Models

Establish entity relationships as foundational data models (stable, serves as architectural blueprint)

<img width="630px" alt="image" src="https://github.com/user-attachments/assets/2656f72e-1af5-467a-96f9-cab95760b720" />

```python
from pydantic import BaseModel

class BaseStory(BaseModel):
    id: int
    name: str
    assignee_id: Optional[int]
    report_to: Optional[int]

class BaseTask(BaseModel):
    id: int
    story_id: int
    name: str
    estimate: int
    done: bool
    assignee_id: Optional[int]

class BaseUser(BaseModel):
    id: int
    name: str
    title: str
```

```python
from aiodataloader import DataLoader
from pydantic_resolve import build_list, build_object

class StoryTaskLoader(DataLoader):
    async def batch_load_fn(self, keys: list[int]):
        tasks = await get_tasks_by_story_ids(keys)
        return build_list(tasks, keys, lambda x: x.story_id)

class UserLoader(DataLoader):
    async def batch_load_fn(self, keys: list[int]):
        users = await get_tuser_by_ids(keys)
        return build_object(users, keys, lambda x: x.id)
```

DataLoader implementations support flexible data sources, from database queries to microservice RPC calls. (It could be replaced in future optimization)

### 2. Compose Business Models

Based on a specific business logic, create domain-specific data structures through selective schemas and relationship dataloader (stable, reusable across use cases)

<img width="630px" alt="image" src="https://github.com/user-attachments/assets/ffc74e60-0670-475c-85ab-cb0d03460813" />

```python
from pydantic_resolve import Loader

class Task(BaseTask):
    user: Optional[BaseUser] = None
    def resolve_user(self, loader=Loader(UserLoader)):
        return loader.load(self.assignee_id) if self.assignee_id else None

class Story(BaseStory):
    tasks: list[Task] = []
    def resolve_tasks(self, loader=Loader(StoryTaskLoader)):
        return loader.load(self.id)

    assignee: Optional[BaseUser] = None
    def resolve_assignee(self, loader=Loader(UserLoader)):
        return loader.load(self.assignee_id) if self.assignee_id else None

    reporter: Optional[BaseUser] = None
    def resolve_reporter(self, loader=Loader(UserLoader)):
        return loader.load(self.report_to) if self.report_to else None
```

Utilize `ensure_subset` decorator for field validation and consistency enforcement:

```python
@ensure_subset(BaseStory)
class Story(BaseModel):
    id: int
    assignee_id: int
    report_to: int

    tasks: list[BaseTask] = []
    def resolve_tasks(self, loader=Loader(StoryTaskLoader)):
        return loader.load(self.id)

```

> Once business models are validated, consider optimizing with specialized queries to replace DataLoader for enhanced performance.

### 3. Implement View-Layer Transformations

Apply presentation-specific modifications and data aggregations (flexible, context-dependent)

Leverage post_field methods for ancestor data access, node transfers, and in-place transformations.

#### Case 1: Aggregate or collect items

<img width="630px" alt="image" src="https://github.com/user-attachments/assets/2e3b1345-9e5e-489b-a81d-dc220b9d6334" />

```python
from pydantic_resolve import Loader, Collector

class Task(BaseTask):
    __pydantic_resolve_collect__ = {'user': 'related_users'}  # Propagate user to collector: 'related_users'

    user: Optional[BaseUser] = None
    def resolve_user(self, loader=Loader(UserLoader)):
        return loader.load(self.assignee_id)

class Story(BaseStory):
    tasks: list[Task] = []
    def resolve_tasks(self, loader=Loader(StoryTaskLoader)):
        return loader.load(self.id)

    assignee: Optional[BaseUser] = None
    def resolve_assignee(self, loader=Loader(UserLoader)):
        return loader.load(self.assignee_id)

    reporter: Optional[BaseUser] = None
    def resolve_reporter(self, loader=Loader(UserLoader)):
        return loader.load(self.report_to)

    # ---------- Post-processing ------------
    related_users: list[BaseUser] = []
    def post_related_users(self, collector=Collector(alias='related_users')):
        return collector.values()
```

#### Case 2: Compute extra fields

<img width="630px" alt="image" src="https://github.com/user-attachments/assets/fd5897d6-1c6a-49ec-aab0-495070054b83" />

```python
class Story(BaseStory):
    tasks: list[Task] = []
    def resolve_tasks(self, loader=Loader(StoryTaskLoader)):
        return loader.load(self.id)

    assignee: Optional[BaseUser] = None
    def resolve_assignee(self, loader=Loader(UserLoader)):
        return loader.load(self.assignee_id)

    reporter: Optional[BaseUser] = None
    def resolve_reporter(self, loader=Loader(UserLoader)):
        return loader.load(self.report_to)

    # ---------- Post-processing ------------
    total_estimate: int = 0
    def post_total_estimate(self):
        return sum(task.estimate for task in self.tasks)
```

### Case 3: Propagate ancestor data through ancestor_context

```python
from pydantic_resolve import Loader

class Task(BaseTask):
    user: Optional[BaseUser] = None
    def resolve_user(self, loader=Loader(UserLoader)):
        return loader.load(self.assignee_id)

    # ---------- Post-processing ------------
    def post_name(self, ancestor_context):  # Access story.name from parent context
        return f'{ancestor_context['story_name']} - {self.name}'

class Story(BaseStory):
    __pydantic_resolve_expose__ = {'name': 'story_name'}

    tasks: list[Task] = []
    def resolve_tasks(self, loader=Loader(StoryTaskLoader)):
        return loader.load(self.id)

    assignee: Optional[BaseUser] = None
    def resolve_assignee(self, loader=Loader(UserLoader)):
        return loader.load(self.assignee_id)

    reporter: Optional[BaseUser] = None
    def resolve_reporter(self, loader=Loader(UserLoader)):
        return loader.load(self.report_to)
```

### 4. Execute Resolution

```python
from pydantic_resolve import Resolver

stories = [Story(**s) for s in await query_stories()]
data = await Resolver().resolve(stories)
```

Complete!

## Technical Architecture

The framework significantly reduces complexity in data composition by maintaining alignment with entity-relationship models, resulting in enhanced maintainability.

> Utilizing an ER-oriented modeling approach delivers 3-5x development efficiency gains and 50%+ code reduction.

Leveraging pydantic's capabilities, it enables GraphQL-like hierarchical data structures while providing flexible business logic integration during data resolution.

Seamlessly integrates with FastAPI to construct frontend-optimized data structures and generate TypeScript SDKs for type-safe client integration.

The core architecture provides `resolve` and `post` method hooks for pydantic and dataclass objects:

- `resolve`: Handles data fetching operations
- `post`: Executes post-processing transformations

This implements a recursive resolution pipeline that completes when all descendant nodes are processed.

![](docs/images/life-cycle.png)

Consider the Sprint, Story, and Task relationship hierarchy:

<img src="docs/images/real-sample.png" style="width: 600px"/>

Upon object instantiation with defined methods, pydantic-resolve traverses the data graph, executes resolution methods, and produces the complete data structure.

DataLoader integration eliminates N+1 query problems inherent in multi-level data fetching, optimizing performance characteristics.

DataLoader architecture enables modular class composition and reusability across different contexts.

Additionally, the framework provides expose and collector mechanisms for sophisticated cross-layer data processing patterns.

## Testing and Coverage

```shell
tox
```

```shell
tox -e coverage
python -m http.server
```

Current test coverage: 97%

## Community

[Discord](https://discord.com/channels/1197929379951558797/1197929379951558800)
