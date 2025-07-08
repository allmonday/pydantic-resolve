[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![PyPI Downloads](https://static.pepy.tech/badge/pydantic-resolve/month)](https://pepy.tech/projects/pydantic-resolve)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)

pydantic-resolve is a sophisticated framework for composing complex data structures with an intuitive, resolver-based architecture that eliminates the N+1 query problem.

it supports:
- pydantic v1
- pydantic v2
- dataclass  `from pydantic.dataclasses import dataclass`

```python
class Task(BaseTask):
    user: Optional[BaseUser] = None
    def resolve_user(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.assignee_id) if self.assignee_id else None

class Story(BaseStory):
    tasks: list[Task] = []
    def resolve_tasks(self, loader=LoaderDepend(StoryTaskLoader)):
        return loader.load(self.id)

```

If you have experience with GraphQL, this article provides comprehensive insights: [Resolver Pattern: A Better Alternative to GraphQL in BFF.](https://github.com/allmonday/resolver-vs-graphql/blob/master/README-en.md)

The framework enables progressive data enrichment through incremental field resolution, allowing seamless API evolution from flat to hierarchical data structures.

Extend your data models by implementing `resolve_field` methods for data fetching and `post_field` methods for transformations, enabling node creation, in-place modifications, or cross-node data aggregation.

Seamlessly integrates with modern Python web frameworks including FastAPI, Litestar, and Django-ninja.


## Installation

```
pip install pydantic-resolve
```

Starting from pydantic-resolve v1.11.0, both pydantic v1 and v2 are supported.

## Documentation

- **Documentation**: https://allmonday.github.io/pydantic-resolve/v2/introduction/
- **Demo Repository**: https://github.com/allmonday/pydantic-resolve-demo
- **Composition-Oriented Pattern**: https://github.com/allmonday/composition-oriented-development-pattern

## Architecture Overview

Building complex data structures requires only 3 systematic steps:

### 1. Define Domain Models

Establish entity relationships as foundational data models (stable, serves as architectural blueprint)

<img width="639" alt="image" src="https://github.com/user-attachments/assets/2656f72e-1af5-467a-96f9-cab95760b720" />

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

DataLoader implementations support flexible data sources, from database queries to microservice RPC calls.

### 2. Compose Business Models

Create domain-specific data structures through selective composition and relationship mapping (stable, reusable across use cases)

<img width="709" alt="image" src="https://github.com/user-attachments/assets/ffc74e60-0670-475c-85ab-cb0d03460813" />

```python
from pydantic_resolve import LoaderDepend

class Task(BaseTask):
    user: Optional[BaseUser] = None
    def resolve_user(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.assignee_id) if self.assignee_id else None

class Story(BaseStory):
    tasks: list[Task] = []
    def resolve_tasks(self, loader=LoaderDepend(StoryTaskLoader)):
        return loader.load(self.id)

    assignee: Optional[BaseUser] = None
    def resolve_assignee(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.assignee_id) if self.assignee_id else None

    reporter: Optional[BaseUser] = None
    def resolve_reporter(self, loader=LoaderDepend(UserLoader)):
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
    def resolve_tasks(self, loader=LoaderDepend(StoryTaskLoader)):
        return loader.load(self.id)

```

> Once business models are validated, consider optimizing with specialized queries to replace DataLoader for enhanced performance.

### 3. Implement View-Layer Transformations

Apply presentation-specific modifications and data aggregations (flexible, context-dependent)

Leverage post_field methods for ancestor data access, node transfers, and in-place transformations.

#### Pattern 1: Aggregate Related Entities

<img width="701" alt="image" src="https://github.com/user-attachments/assets/2e3b1345-9e5e-489b-a81d-dc220b9d6334" />

```python
from pydantic_resolve import LoaderDepend, Collector

class Task(BaseTask):
    __pydantic_resolve_collect__ = {'user': 'related_users'}  # Propagate user to collector: 'related_users'

    user: Optional[BaseUser] = None
    def resolve_user(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.assignee_id)

class Story(BaseStory):
    tasks: list[Task] = []
    def resolve_tasks(self, loader=LoaderDepend(StoryTaskLoader)):
        return loader.load(self.id)

    assignee: Optional[BaseUser] = None
    def resolve_assignee(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.assignee_id)

    reporter: Optional[BaseUser] = None
    def resolve_reporter(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.report_to)

    # ---------- Post-processing ------------
    related_users: list[BaseUser] = []
    def post_related_users(self, collector=Collector(alias='related_users')):
        return collector.values()
```

#### Pattern 2: Compute Derived Metrics

<img width="687" alt="image" src="https://github.com/user-attachments/assets/fd5897d6-1c6a-49ec-aab0-495070054b83" />

```python
class Story(BaseStory):
    tasks: list[Task] = []
    def resolve_tasks(self, loader=LoaderDepend(StoryTaskLoader)):
        return loader.load(self.id)

    assignee: Optional[BaseUser] = None
    def resolve_assignee(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.assignee_id)

    reporter: Optional[BaseUser] = None
    def resolve_reporter(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.report_to)

    # ---------- Post-processing ------------
    total_estimate: int = 0
    def post_total_estimate(self):
        return sum(task.estimate for task in self.tasks)
```

### Pattern 3: Propagate Ancestor Context

```python
from pydantic_resolve import LoaderDepend

class Task(BaseTask):
    user: Optional[BaseUser] = None
    def resolve_user(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.assignee_id)

    # ---------- Post-processing ------------
    def post_name(self, ancestor_context):  # Access story.name from parent context
        return f'{ancestor_context['story_name']} - {self.name}'

class Story(BaseStory):
    __pydantic_resolve_expose__ = {'name': 'story_name'}

    tasks: list[Task] = []
    def resolve_tasks(self, loader=LoaderDepend(StoryTaskLoader)):
        return loader.load(self.id)

    assignee: Optional[BaseUser] = None
    def resolve_assignee(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.assignee_id)

    reporter: Optional[BaseUser] = None
    def resolve_reporter(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.report_to)
```

### 4. Execute Resolution Pipeline

```python
from pydantic_resolve import Resolver

stories: List[Story] = await query_stories()
await Resolver().resolve(stories)
```

Resolution complete!

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

## Benchmark

`ab -c 50 -n 1000` based on FastAPI.

strawberry-graphql

```
Server Software:        uvicorn
Server Hostname:        localhost
Server Port:            8000

Document Path:          /graphql
Document Length:        5303 bytes

Concurrency Level:      50
Time taken for tests:   3.630 seconds
Complete requests:      1000
Failed requests:        0
Total transferred:      5430000 bytes
Total body sent:        395000
HTML transferred:       5303000 bytes
Requests per second:    275.49 [#/sec] (mean)
Time per request:       181.498 [ms] (mean)
Time per request:       3.630 [ms] (mean, across all concurrent requests)
Transfer rate:          1460.82 [Kbytes/sec] received
                        106.27 kb/s sent
                        1567.09 kb/s total

Connection Times (ms)
              min  mean[+/-sd] median   max
Connect:        0    0   0.2      0       1
Processing:    31  178  14.3    178     272
Waiting:       30  176  14.3    176     270
Total:         31  178  14.4    179     273
```

pydantic-resolve

```
Server Software: uvicorn
Server Hostname: localhost
Server Port: 8000

Document Path: /sprints
Document Length: 4621 bytes

Concurrency Level: 50
Time taken for tests: 2.194 seconds
Complete requests: 1000
Failed requests: 0
Total transferred: 4748000 bytes
HTML transferred: 4621000 bytes
Requests per second: 455.79 [#/sec] (mean)
Time per request: 109.700 [ms] (mean)
Time per request: 2.194 [ms] (mean, across all concurrent requests)
Transfer rate: 2113.36 [Kbytes/sec] received

Connection Times (ms)
min mean[+/-sd] median max
Connect: 0 0 0.3 0 1
Processing: 30 107 10.9 106 138
Waiting: 28 105 10.7 104 138
Total: 30 107 11.0 106 140
```

## Community

[Discord](https://discord.com/channels/1197929379951558797/1197929379951558800)
