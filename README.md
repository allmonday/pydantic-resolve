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

If you have experience with GraphQL, this article provides comprehensive insights: [Resolver Pattern: A Better Alternative to GraphQL in BFF (api-integration).](https://github.com/allmonday/resolver-vs-graphql/blob/master/README-en.md)

It could be seamlessly integrated with modern Python web frameworks including FastAPI, Litestar, and Django-ninja.

## Hello world

Here is the root data we have, it belongs to type BaseStory:

```python
base_stories = [
  BaseStory(id=1, name="story - 1"),
  BaseStory(id=2, name="story - 2")
]
```

First let's define Story, which inherit from BaseStory, and add tasks field.

All the details of query process are encapsulated inside the dataloader, no worry about N+1 query.

```python
from pydantic_resolve import Resolver
from biz_models import BaseTask, BaseStory, BaseUser
from biz_services import UserLoader, StoryTaskLoader

class Story(BaseStory):
    tasks: list[BaseTask] = []
    def resolve_tasks(self, loader=Loader(StoryTaskLoader)): # StoryTaskLoader return list of BaseTasks of each story by story_id
        return loader.load(self.id)

stories = [Story.model_validate(s, from_attributes=True) for s in base_stories]
data = await Resolver().resolve(stories)
```

Then the json output of data looks like:

```json
[
  {
    "id": 1,
    "name": "story - 1",
    "tasks": [
      {
        "id": 1,
        "name": "design",
        "user_id": 2
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
        "user_id": 2
      }
    ]
  }
]
```

If you continue extend the BaseTask and replace the return type of Story.tasks

```python
class Task(BaseTask):
    user: Optional[BaseUser] = None
    def resolve_user(self, loader=Loader(UserLoader)):
        return loader.load(self.assignee_id) if self.assignee_id else None

class Story(BaseStory):
    tasks: list[Task] = [] # BaseTask -> Task
    def resolve_tasks(self, loader=Loader(StoryTaskLoader)):
        return loader.load(self.id)
```

You will get the user info immediately.

```json
[
  {
    "id": 1,
    "name": "story - 1",
    "tasks": [
      {
        "id": 1,
        "name": "design",
        "user_id": 1,
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
        "user_id": 2,
        "user": {
          "id": 2,
          "name": "john"
        }
      }
    ]
  }
]
```

With `openapi-ts` you could transfer those types to the clients seamlessly.

## Installation

```
pip install pydantic-resolve
```

Starting from pydantic-resolve v1.11.0, both pydantic v1 and v2 are supported.

## Documentation

- **Documentation**: https://allmonday.github.io/pydantic-resolve/
- **Demo**: https://github.com/allmonday/pydantic-resolve-demo
- **Composition-Oriented Pattern**: https://github.com/allmonday/composition-oriented-development-pattern

## 3 Steps to construct complex data

Let's take Agile's Story for example.

### 1. Define Domain Models

Establish entity relationships as foundational data models

(which is stable, serves as architectural blueprint)

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

Based on a our business logic, create domain-specific data structures through selective schemas and relationship dataloader

We need to extend `tasks`, `assignee` and `reporter` for `Story`, extend `user` for `Task`

Extending new fields is dynamic, all based on business requirement, but the relationships / loader are restricted by the definition from step 1.

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

> Once this combination is stable, you can consider optimizing with specialized queries to replace DataLoader for enhanced performance, eg ORM's join relationship

### 3. Implement View-Layer Transformations

Dataset from data-persistent layer can not meet all requirements, we always need some extra computed fields or adjust the data structure.

post method could read fields from ancestor, collect fields from descendants or modify the data fetched by resolve method.

#### Case 1: Aggregate or collect items

<img width="630px" alt="image" src="https://github.com/user-attachments/assets/2e3b1345-9e5e-489b-a81d-dc220b9d6334" />

`__pydantic_resolve_collect__` can collect fields from current node and then send them to ancestor node who declared `related_users`.

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

post methods are executed after all resolve_methods are resolved, so we can use it to calculate extra fields.

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

`__pydantic_resolve_expose__` could expose specific fields from current node to it's descendant.

alias_names should be global unique inside root node.

descendant nodes could read the value with `ancestor_context[alias_name]`.

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

### 4. Execute Resolver().resolve()

```python
from pydantic_resolve import Resolver

stories = [Story(**s) for s in await query_stories()]
data = await Resolver().resolve(stories)
```

`query_stories()` returns `BaseStory` list, after we transformed it into `Story`, resolve and post fields are initialized as default value, after `Resolver().resolve()` finished, all these fields will be resolved and post-processed to what we expected.

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
