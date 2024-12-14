[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![Downloads](https://static.pepy.tech/personalized-badge/pydantic-resolve?period=month&units=abbreviation&left_color=grey&right_color=orange&left_text=Downloads)](https://pepy.tech/project/pydantic-resolve)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)

<img style="width:420px;" src="./docs/images/resolver.png"></img>

pydantic-resolve is a lightweight wrapper library based on pydantic. It adds resolve and post methods to pydantic and dataclass objects.

If you have ever written similar code and felt unsatisfied, pydantic-resolve can come in handy.

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

It can split the processing into two parts: describing the data and loading the data, making the combination of data calculations clearer and more maintainable.

```python
@model_config()
class Story(Base.Story)

    tasks: List[Task] = Field(default_factory=list, exclude=True)
    def resolve_tasks(self, loader=LoaderDepend(TaskLoader)):
        return loader.load(self.id)

    total_task_time: int = 0
    def post_total_task_time(self):
        return sum(task.time for task in self.tasks)

    total_done_task_time: int = 0
    def post_total_done_task_time(self):
        return sum(task.time for task in self.tasks if task.done)
  
await Resolver().resolve(stories)
```

It can reduce the code complexity in the data assembly process, making the code closer to the ER model and more maintainable.

With the help of pydantic, it can describe data structures in a graph-like relationship like GraphQL, and can also make adjustments based on business needs while fetching data.

It can easily cooperate with FastAPI to build frontend friendly data structures on the backend and provide them to the frontend in the form of a TypeScript SDK.

> Using an ERD-oriented modeling approach, it can provide you with a 3 to 5 times increase in development efficiency and reduce code volume by more than 50%.

It provides resolve and post methods for pydantic objects.

- resolve is usually used to fetch data
- post can be used to do additional processing after fetching data

```python
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
    author = book_author_mapping[book_name]
    return Person(**[person for person in persons if person['name'] == author][0])

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

When the object methods are defined and the objects are initialized, pydantic-resolve will internally traverse the data, execute these methods to process the data, and finally obtain all the data.

```python
[
    Book(title='1984', year=1949, author=Person(name='George Orwell', age=46)),
    Book(title='To Kill a Mockingbird', year=1960, author=Person(name='Harper Lee', age=89)),
    Book(title='The Great Gatsby', year=1925, author=Person(name='F. Scott Fitzgerald', age=44))
]
```

Compared to procedural code, it requires traversal and additional maintenance of concurrency logic.

```python
import asyncio

async def handle_author(book: Book):
    author = await get_author(book.title)
    book.author = author

await asyncio.gather(*[handle_author(book) for book in books])
```

With DataLoader, pydantic-resolve can avoid the N+1 query problem that easily occurs when fetching data in multiple layers, optimizing performance.

Using DataLoader also allows the defined class fragments to be reused in any location.

In addition, it also provides expose and collector mechanisms to facilitate cross-layer data processing.

## Installation

```
pip install pydantic-resolve
```

Starting from pydantic-resolve v1.11.0, it will be compatible with both pydantic v1 and v2.

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

## Sponsor

If this code helps and you wish to support me

Paypal: https://www.paypal.me/tangkikodo

## Discussion

[Discord](https://discord.com/channels/1197929379951558797/1197929379951558800)
