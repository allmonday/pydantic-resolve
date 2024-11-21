# Introduction

pydantic-resolve is a lightweight wrapper library based on pydantic, which can greatly simplify the complexity of building data.

It can provide you with a 3 to 5 times improvement in development efficiency and reduce more than 50% of the code.

It offers `resolve` and `post` methods for pydantic objects.

```python
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

After defining the object methods and initializing the objects, pydantic-resolve will internally traverse the data and execute these methods to process the data.

With the help of dataloader, pydantic-resolve can avoid the N+1 query problem that often occurs when fetching data in multiple layers, optimizing performance.

In addition, it also provides `expose` and `collector` mechanisms to facilitate cross-layer data processing.

## Installation

```
pip install pydantic-resolve
```

Starting from pydantic-resolve v1.11.0, it will be compatible with both pydantic v1 and v2.
