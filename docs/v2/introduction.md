# Introduction

pydantic-resolve is a lightweight wrapper library based on pydantic, which can greatly simplify the complexity of building data.

With the help of pydantic, it can describe data structures using graph relationships like GraphQL, and also make adjustments based on business requirements while fetching data.

Using an ER-oriented modeling approach, it can provide you with a 3 to 5 times increase in development efficiency and reduce code volume by more than 50%.

It offers `resolve` and `post` methods for pydantic objects.

```python
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
        Child(id=1, name="Titan"), Child(id=1, name="Siri")])
```

`resolve` is usually used to fetch data, while `post` can perform additional processing after fetching the data.

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

After defining the object methods and initializing the objects, pydantic-resolve will internally traverse the data and execute these methods to process the data.

With the help of dataloader, pydantic-resolve can avoid the N+1 query problem that often occurs when fetching data in multiple layers, optimizing performance.

In addition, it also provides `expose` and `collector` mechanisms to facilitate cross-layer data processing.

## Installation

```
pip install pydantic-resolve
```

Starting from pydantic-resolve v1.11.0, it will be compatible with both pydantic v1 and v2.
