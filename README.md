[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![PyPI Downloads](https://static.pepy.tech/badge/pydantic-resolve/month)](https://pepy.tech/projects/pydantic-resolve)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)

pydantic-resolve is a tool helps to flexibly assemble complex view objects, it's the most intuitive one.

```python
class Task(BaseTask):
    user: Optional[BaseUser] = None
    def resolve_user(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.assignee_id) if self.assignee_id else None
```

If you are have ever use GraphQL, this article will explain more in details [Resolver Pattern: A Better Alternative to GraphQL in BFF.](https://github.com/allmonday/resolver-vs-graphql/blob/master/README-en.md)

It can progressively extends the data, adding new fields, so you can gradually upgrade your api result from flat to nested.

You'll be able to simply extend your data by adding `resolve_field` function, and then create new node, in-place modify the node or moving them to ancestor nodes by adding `post_field` function.

It plays pretty well with FastAPI / Litestar / Django-ninja web frameworks

> dataclass is also supported

## Installation

```
pip install pydantic-resolve
```

Starting from pydantic-resolve v1.11.0, it suports both pydantic v1 and v2.

## Documents

- **Doc**: https://allmonday.github.io/pydantic-resolve/v2/introduction/
- **Demo**: https://github.com/allmonday/pydantic-resolve-demo
- **Composition oriented pattern**: https://github.com/allmonday/composition-oriented-development-pattern

## Introduction

It will take only 3 steps to build to the view object from simple to complex.

### 1. Design ER model

This is how we define the entities and their relationships. (very stable, act as blueprint)

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

Inside DataLoader, you could adopt whatever tech-stacks you like, from DB query to RPC.

### 1. Build business model for specific use case

This is what we really need in a specific business scenario, pick and link. (stable, and can be reused)

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

you can also pick fields and decorate it with `ensure_subset` to check the consistence

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

> Once the business model is validated as useful, more efficient (but complex) queries can be used to replace DataLoader.

### 3. Tweak the view model

Here we can do extra modifications for view layer. (flexible, case by case)

using post_field method, you can read values from ancestor node, transfer nodes to ancestor, or any in-place modifications.

more information, please refer to [How it works?](#how-it-works)

#### case 1: collect related users for each story

<img width="701" alt="image" src="https://github.com/user-attachments/assets/2e3b1345-9e5e-489b-a81d-dc220b9d6334" />

```python
from pydantic_resolve import LoaderDepend, Collector

class Task(BaseTask):
    __pydantic_resolve_collect__ = {'user': 'related_users'}  # send user to collector: 'related_users'

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

    # ---------- post method ------------
    related_users: list[BaseUser] = []
    def post_related_users(self, collector=Collector(alias='related_users')):
        return collector.values()
```

#### case 2: sum up estimate time for each story

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

    # ---------- post method ------------
    total_estimate: int = 0
    def post_total_estimate(self):
        return sum(task.estimate for task in self.tasks)
```

### case 3: expose ancestor field to descents

```python
from pydantic_resolve import LoaderDepend

class Task(BaseTask):
    user: Optional[BaseUser] = None
    def resolve_user(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.assignee_id)

    # ---------- post method ------------
    def post_name(self, ancestor_context):  # read story.name from direct ancestor
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

### 4. Resolve and get the result

```python
from pydantic_resolve import Resolver

stories: List[Story] = await query_stories()
await Resolver().resolve(stories)
```

done!

## How it works?

It can reduce the code complexity during the data composition, making the code close to the ER model and then more maintainable.

> Using an ER oriented modeling approach, it can provide us with a 3 to 5 times increase in development efficiency and reduce code by more than 50%.

With the help of pydantic, it can describe data structures in a graph-like relationship like GraphQL, and can also make adjustments based on business needs while fetching data.

It can easily run with FastAPI to build frontend friendly data structures on the backend and provide them to the frontend in the form of a TypeScript SDK.

Basically it just provides resolve and post methods for pydantic and dataclass objects.

- resolve is used to fetch data
- post is used to do additional processing after fetching data

And this is a recursive process, the resolve process finishs after all descendants are done.

![](docs/images/life-cycle.png)

take Sprint, Story and Task for example:

<img src="docs/images/real-sample.png" style="width: 600px"/>

When the object methods are defined and the objects are initialized, pydantic-resolve will internally traverse the data, execute these methods to process the data, and finally obtain all the data.

With DataLoader, pydantic-resolve can avoid the N+1 query problem that easily occurs when fetching data in multiple layers, optimizing performance.

Using DataLoader also allows the defined class fragments to be reused in any location.

In addition, it also provides expose and collector mechanisms to facilitate cross-layer data processing.

## Test and coverage

```shell
tox
```

```shell
tox -e coverage
python -m http.server
```

latest coverage: 97%

## Hear your voice

[Discord](https://discord.com/channels/1197929379951558797/1197929379951558800)
