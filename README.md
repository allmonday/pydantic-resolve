[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![PyPI Downloads](https://static.pepy.tech/badge/pydantic-resolve/month)](https://pepy.tech/projects/pydantic-resolve)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)

**Whether the process of data transformation is intuitive is one of the determining factors of project quality.**

pydantic-resolve turns pydantic from a static data container into a powerful dynamic computing tool.

It provides major features based on pydantic class:
- pluggable resolve methods and post methods, to define how to fetch and modify nodes.
- transporting field data from ancestor nodes to their descendant nodes.
- collecting data from any descendants nodes to their ancestor nodes.

It supports:

- pydantic v1
- pydantic v2
- dataclass `from pydantic.dataclasses import dataclass`

It could be seamlessly integrated with modern Python web frameworks including FastAPI, Litestar, and Django-ninja.

For **FastAPI**, we can explore the dependencies of schemas with [fastapi-voyager](https://github.com/allmonday/fastapi-voyager)

![](https://private-user-images.githubusercontent.com/2917822/497147536-a6ccc9f1-cf06-493a-b99b-eb07767564bd.png?jwt=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3NTk2NjUzNzQsIm5iZiI6MTc1OTY2NTA3NCwicGF0aCI6Ii8yOTE3ODIyLzQ5NzE0NzUzNi1hNmNjYzlmMS1jZjA2LTQ5M2EtYjk5Yi1lYjA3NzY3NTY0YmQucG5nP1gtQW16LUFsZ29yaXRobT1BV1M0LUhNQUMtU0hBMjU2JlgtQW16LUNyZWRlbnRpYWw9QUtJQVZDT0RZTFNBNTNQUUs0WkElMkYyMDI1MTAwNSUyRnVzLWVhc3QtMSUyRnMzJTJGYXdzNF9yZXF1ZXN0JlgtQW16LURhdGU9MjAyNTEwMDVUMTE1MTE0WiZYLUFtei1FeHBpcmVzPTMwMCZYLUFtei1TaWduYXR1cmU9ZThlNjVmMWIwMjYzOTVmZTRiYmExNTdhM2IyZGYzNTIyNzJkMjM1ZDBlNWU4ZDRlMGMyNDZiOGI5M2I3NGM4ZSZYLUFtei1TaWduZWRIZWFkZXJzPWhvc3QifQ.blswuM08hTfJx_wDjUbul0O5dg9E5UzyUlljOt0PHek)


## Installation

```
pip install pydantic-resolve
```

Starting from pydantic-resolve v1.11.0, both pydantic v1 and v2 are supported.


## Documentation

- **Documentation**: https://allmonday.github.io/pydantic-resolve/
- **Demo**: https://github.com/allmonday/pydantic-resolve-demo
- **Composition-Oriented Pattern**: https://github.com/allmonday/composition-oriented-development-pattern
- [Resolver Pattern: A Better Alternative to GraphQL in BFF (api-integration).](https://github.com/allmonday/resolver-vs-graphql/blob/master/README-en.md)


## Hello world

Here is the root data, a list of `BaseStory`.

```python
base_stories = [
  BaseStory(id=1, name="story - 1"),
  BaseStory(id=2, name="story - 2")
]
```

let's import Resolver and resolve the base_stories, currently `Resolver().resolve` will do nothing becuase pydantic-resolve related configuration is not applied yet.

```python
from pydantic_resolve import Resolver

data = await Resolver().resolve(base_stories)
```

Then let's define the `Story`, which inherit from `BaseStory`, add `tasks` field.

Now let's define `resolve_tasks` method and use `StoryTskLoader` to load the tasks (inside DataLoader it will gather the ids and run query in batch)

Let's initialize `stories` from `base_stories`

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

Here is where magic happens, let's check the data (in json), the `tasks` field are fetched automatically:

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

Let's continue extend the `BaseTask` and replace the return type of `Story.tasks`

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

Then user data is available immediately.

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

That's the basic sample of `resolve_method` in fetching related data.


## Construct complex data in 3 steps

Let's take Agile's model for example, it includes Story, Task and Member

### 1. Define Domain Models

Establish entity relationships model based on business concept.

> which is stable, serves as architectural blueprint

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

The dataloader is defined for general usage, if other approach such as ORM relationship is available, it can be easily replaced.
DataLoader's implementation supports all kinds of data sources, from database queries to microservice RPC calls.

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


### 2. Compose Business Models

Based on a our business logic, create domain-specific data structures through schemas and relationship dataloader

We just need to extend `tasks`, `assignee` and `reporter` for `Story`, and extend `user` for `Task`

Extending new fields is dynamic, depends on business requirement, however the relationships / loaders are restricted by the definition in step 1.

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

`ensure_subset` decorator is a helper function which ensures the target class's fields (without default value) are strictly subset of class in parameter.

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

> Once this combination is stable, you can consider optimizing with specialized queries to replace DataLoader for enhanced performance, such as ORM's join relationship

### 3. Implement View Model Transformations

Dataset from data-persistent layer can not meet all requirements for view model, adding extra computed fields or adjusting current data is very common.

`post_method` is what you need, it is triggered after all descendant nodes are resolved.

It could read fields from ancestor, collect fields from descendants or modify the data fetched by resolve method.

Let's show them case by case.

#### #1: Aggregate and collect items

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

#### #2: Compute extra fields

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

### #3: Propagate ancestor data through ancestor_context

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
