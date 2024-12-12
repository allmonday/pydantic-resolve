# Introduction

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
```

It can reduce the complexity of the code for obtaining and adjusting data during the data assembly process, making the code closer to the ER model and more maintainable.

With the help of pydantic, it can describe data structures in a graph-like manner, similar to GraphQL, and can also make adjustments based on business needs while obtaining data.

It can easily cooperate with FastAPI to build front-end friendly data structures on the backend and provide them to the front-end in the form of a TypeScript SDK.

> Using an ERD-oriented modeling approach, it can provide you with a 3 to 5 times increase in development efficiency and reduce code volume by more than 50%.

It provides resolve and post methods for pydantic objects.

- [resolve](./api.zh.md#resolve) is usually used to obtain data
- [post](./api.zh.md#post) can be used to perform additional processing after obtaining data

```python hl_lines="13 17"
from pydantic import BaseModel
from pydantic_resolve import Resolver
class Car(BaseModel):
    id: int
    name: str
    produced_by: str

class Child(BaseModel):
    id: int
    name: str

    cars: List[Car] = []
    async def resolve_cars(self):
        return await get_cars_by_child(self.id)

    description: str = ''
    def post_description(self):
        desc = ', '.join([c.name for c in self.cars])
        return f'{self.name} owns {len(self.cars)} cars, they are: {desc}'

children = await Resolver.resolve([
        Child(id=1, name="Titan"),
        Child(id=1, name="Siri")]
    )

```

After defining the object methods and initializing the objects, pydantic-resolve will internally traverse the data, execute these methods to process the data, and finally obtain all the data.

```python
[
    Child(id=1, name="Titan", cars=[
        Car(id=1, name="Focus", produced_by="Ford")],
        description="Titan owns 1 cars, they are: Focus"),
    Child(id=1, name="Siri", cars=[
        Car(id=3, name="Seal", produced_by="BYD")],
        description="Siri owns 1 cars, they are Seal")
]
```

In contrast, procedural code requires traversal and additional maintenance of concurrency logic.

```python
import asyncio

async def handle_child(child):
    cars = await get_cars()
    child.cars = cars

    cars_desc = '.'.join([c.name for c in cars])
    child.description = f'{child.name} owns {len(child.cars)} cars, they are: {car_desc}'

tasks = []
for child in children:
    tasks.append(handle(child))

await asyncio.gather(*tasks)
```


With DataLoader, pydantic-resolve can avoid the N+1 query problem that easily occurs when fetching data in multiple layers, optimizing performance.

Using DataLoader also allows the defined class fragments to be reused in any location.

In addition, it provides [expose](./api.zh.md#ancestor_context) and [collector](./api.zh.md#collector) mechanisms to facilitate cross-layer data processing.

## Installation

```
pip install pydantic-resolve
```

Starting from pydantic-resolve v1.11.0, it will be compatible with both pydantic v1 and v2.
