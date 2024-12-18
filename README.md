[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![Downloads](https://static.pepy.tech/personalized-badge/pydantic-resolve?period=month&units=abbreviation&left_color=grey&right_color=orange&left_text=Downloads)](https://pepy.tech/project/pydantic-resolve)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)

<img style="width:420px;" src="./docs/images/resolver.png"></img>

pydantic-resolve is a lightweight wrapper library based on pydantic, It adds resolve and post methods to pydantic and dataclass objects.

It aims to provide a more elegant way for data composining, helps developers focusing on the core business logic.

## Problems to solve

If you have ever seen similar code and felt unsatisfied, pydantic-resolve can come in handy.

```python
story_ids = [s.id for s in stories]
tasks = await get_all_tasks_by_story_ids(story_ids)

story_tasks = defaultdict(list)

for task in tasks:
    story_tasks[task.story_id].append(task)

for story in stories:
    tasks = story_tasks.get(story.id, [])
    story.total_task_time = sum(task.time for task in tasks)
    story.total_done_tasks_time = sum(task.time for task in tasks if task.done)
```

This snippet mixed data fetching, traversal, temp variables and **business logic** together, just for one level of relationships.

pydantic-resolve can help **split them apart**, let you focus on the core business logic.

```python
from pydantic_resolve import Resolver, LoaderDepend, build_list
from aiodataloader import DataLoader

# data fetching
class TaskLoader(DataLoader):
    async def batch_load_fn(self, story_ids):
        tasks = await get_all_tasks_by_story_ids(story_ids)
        return build_list(tasks, story_ids, lambda t: t.story_id)

# core business logics
class Story(Base.Story):
    # fetch tasks
    tasks: List[Task] = []
    def resolve_tasks(self, loader=LoaderDepend(TaskLoader)):
        return loader.load(self.id)

    # calc after fetched
    total_task_time: int = 0
    def post_total_task_time(self):
        return sum(task.time for task in self.tasks)

    total_done_task_time: int = 0
    def post_total_done_task_time(self):
        return sum(task.time for task in self.tasks if task.done)

# traversal and execute methods (runner)
await Resolver().resolve(stories)
```

pydantic-resolve can be easily applied to more complicated scenarios, such as:

A list of sprint, each sprint owns a list of story, each story owns a list of task, and do some modifications or calculations.

- no more temp variables
- no more traversals 
- no more indents

Just focus on the target you want to handle, and you can **easily plug in and out the related fields without changing other code**.

TOTALLY COMPOSABLE.

```python
# data fetching
class TaskLoader(DataLoader):
    async def batch_load_fn(self, story_ids):
        tasks = await get_all_tasks_by_story_ids(story_ids)
        return build_list(tasks, story_ids, lambda t: t.story_id)

class StoryLoader(DataLoader):
    async def batch_load_fn(self, sprint_ids):
        stories = await get_all_stories_by_sprint_ids(sprint_ids)
        return build_list(stories, sprint_ids, lambda t: t.sprint_id)

# core business logic
class Story(Base.Story):
    tasks: List[Task] = []
    def resolve_tasks(self, loader=LoaderDepend(TaskLoader)):
        return loader.load(self.id)

    total_task_time: int = 0
    def post_total_task_time(self):
        return sum(task.time for task in self.tasks)

    total_done_task_time: int = 0
    def post_total_done_task_time(self):
        return sum(task.time for task in self.tasks if task.done)

class Sprint(Base.Sprint):
    stories: List[Story] = []
    def resolve_stories(self, loader=LoaderDepend(StoryLoader)):
        return loader.load(self.id)

    total_time: int = 0
    def post_total_time(self):
        return sum(story.total_task_time for story in self.stories)

    total_done_time: int = 0
    def post_total_done_time(self):
        return sum(story.total_done_task_time for story in self.stories)


# traversal and execute methods (runner)
await Resolver().resolve(sprints)
```

Compares to ...

```python
sprint_ids = [s.id for s in sprints]
stories = await get_all_stories_by_sprint_id(sprint_ids)

story_ids = [s.id for s in stories]
tasks = await get_all_tasks_by_story_ids(story_ids)

sprint_stories = defaultdict(list)
story_tasks = defaultdict(list)

for story in stories:
    sprint_stories[story.sprint_id].append(story)

for task in tasks:
    story_tasks[task.story_id].append(task)

for sprint in sprints:
    stories = sprint_stories.get(sprint.id, [])
    sprint.stories = stories

    for story in stories:
        tasks = story_tasks.get(story.id, [])
        story.total_task_time = sum(task.time for task in tasks)
        story.total_done_task_time = sum(task.time for task in tasks if task.done)

    sprint.total_time = sum(story.total_task_time for story in stories) 
    sprint.total_done_time = sum(story.total_done_task_time for story in stories)
```

## Features

It can reduce the code complexity in the data assembly process, making the code closer to the ER model and more maintainable.

> Using an ER oriented modeling approach, it can provide you with a 3 to 5 times increase in development efficiency and reduce code volume by more than 50%.

With the help of pydantic, it can describe data structures in a graph-like relationship like GraphQL, and can also make adjustments based on business needs while fetching data.

It can easily run with FastAPI to build frontend friendly data structures on the backend and provide them to the frontend in the form of a TypeScript SDK.

Basically it just provides resolve and post methods for pydantic and dataclass objects.

- resolve is used to fetch data
- post is used to do additional processing after fetching data

And this is a recursive process, the resolve process finishs after all descendants are done.

![](docs/images/life-cycle.png)

take Sprint, Story and Task for example:

<img src="docs/images/real-sample.png" style="width: 600px"/>
![](docs/images/real-sample.png)

When the object methods are defined and the objects are initialized, pydantic-resolve will internally traverse the data, execute these methods to process the data, and finally obtain all the data.

With DataLoader, pydantic-resolve can avoid the N+1 query problem that easily occurs when fetching data in multiple layers, optimizing performance.

Using DataLoader also allows the defined class fragments to be reused in any location.

In addition, it also provides expose and collector mechanisms to facilitate cross-layer data processing.

## Installation

```
pip install pydantic-resolve
```

Starting from pydantic-resolve v1.11.0, it will be compatible with both pydantic v1 and v2.

## Hello world sample

originally we have list of books, then we want to attach the author info.

```python
import asyncio
from pydantic_resolve import Resolver

# data
books = [
    {"title": "1984", "year": 1949},
    {"title": "To Kill a Mockingbird", "year": 1960},
    {"title": "The Great Gatsby", "year": 1925}]

persons = [
    {"name": "George Orwell", "age": 46},
    {"name": "Harper Lee", "age": 89},
    {"name": "F. Scott Fitzgerald", "age": 44}]

book_author_mapping = {
    "1984": "George Orwell",
    "To Kill a Mockingbird": "Harper Lee",
    "The Great Gatsby": "F. Scott Fitzgerald"}

async def get_author(title: str) -> Person:
    await asyncio.sleep(0.1)
    author_name = book_author_mapping[title]
    if not author_name:
        return None
    author = [person for person in persons if person['name'] == author_name][0]
    return Person(**author)

class Person(BaseModel):
    name: str
    age: int


class Book(BaseModel):
    title: str
    year: int
    author: Optional[Person] = None

    async def resolve_author(self):
        return await get_author(self.title)

books = [Book(**book) for book in books]
books_with_author = await Resolver().resolve(books)

```

output

```python
[
    Book(title='1984', year=1949, author=Person(name='George Orwell', age=46)),
    Book(title='To Kill a Mockingbird', year=1960, author=Person(name='Harper Lee', age=89)),
    Book(title='The Great Gatsby', year=1925, author=Person(name='F. Scott Fitzgerald', age=44))
]
```

internally, it runs concurrently to execute the async functions, which looks like:

```python
import asyncio

async def handle_author(book: Book):
    author = await get_author(book.title)
    book.author = author

await asyncio.gather(*[handle_author(book) for book in books])
```

## Documents

- **Demo**: https://github.com/allmonday/pydantic-resolve-demo
- **Composition oriented pattern**: https://github.com/allmonday/composition-oriented-development-pattern

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
