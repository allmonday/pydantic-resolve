# Introduction

pydantic-resolve is a lightweight wrapper library based on pydantic. It adds resolve and post methods to pydantic and dataclass objects.

It can reduce the code complexity in the data assembly process, making the code closer to the ER model and more maintainable.

With the help of pydantic, it can describe data structures in a graph-like relationship like GraphQL, and can also make adjustments based on business needs while fetching data.

It can easily cooperate with FastAPI to build frontend friendly data structures on the backend and provide them to the front-end in the form of a TypeScript SDK.

> Using an ERD-oriented modeling approach, it can provide you with a 3 to 5 times increase in development efficiency and reduce code volume by more than 50%.

It provides resolve and post methods for pydantic objects.

- [resolve](./api.md#resolve) is usually used to fetch data
- [post](./api.md#post) can be used to do additional processing after fetching data

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

When the object methods are defined and the objects are initialized, pydantic-resolve will internally traverse the data, execute these methods to process the data, and finally obtain all the data.

```python
[
    Child(id=1, name="Titan", cars=[
        Car(id=1, name="Focus", produced_by="Ford")],
        description="Titan owns 1 cars, they are: Focus"
        ),
    Child(id=1, name="Siri", cars=[
        Car(id=3, name="Seal", produced_by="BYD")],
        description="Siri owns 1 cars, they are Seal")
]
```

Compared to procedural code, it requires traversal and additional maintenance of concurrency logic.

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

In addition, it also provides [expose](./api.md#ancestor_context) and [collector](./api.md#collector) mechanisms to facilitate cross-layer data processing.

## Installation

```
pip install pydantic-resolve
```

Starting from pydantic-resolve v1.11.0, it will be compatible with both pydantic v1 and v2.
