# Pydantic-resolve

[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
![Test Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/allmonday/6f1661c6310e1b31c9a10b0d09d52d11/raw/covbadge.json)
[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![Downloads](https://static.pepy.tech/personalized-badge/pydantic-resolve?period=month&units=abbreviation&left_color=grey&right_color=orange&left_text=Downloads)](https://pepy.tech/project/pydantic-resolve)

> A small yet powerful package which can run resolvers to generate deep nested datasets.

**example**:

```python
# define loader functions
async def friends_batch_load_fn(names):
    mock_db = {
        'tangkikodo': ['tom', 'jerry'],
        'john': ['mike', 'wallace'],
        'trump': ['sam', 'jim'],
        'sally': ['sindy', 'lydia'],
    }
    return [mock_db.get(name, []) for name in names]

async def contact_batch_load_fn(names):
    mock_db = {
        'tom': 100, 'jerry':200, 'mike': 3000, 'wallace': 400, 'sam': 500,
        'jim': 600, 'sindy': 700, 'lydia': 800, 'tangkikodo': 900, 'john': 1000,
        'trump': 1200, 'sally': 1300,
    }
    return [mock_db.get(name, None) for name in names]

# define schemas
class Contact(BaseModel):
    number: Optional[int]

class Friend(BaseModel):
    name: str

    contact: int = 0
    @mapper(lambda n: Contact(number=n))
    def resolve_contact(self, loader=LoaderDepend(contact_batch_load_fn)):
        return loader.load(self.name)

class User(BaseModel):
    name: str
    age: int

    greeting: str = ''
    def resolve_greeting(self):
        return f"hello, i'm {self.name}, {self.age} years old."

    contact: int = 0
    @mapper(lambda n: Contact(number=n))
    def resolve_contact(self, loader=LoaderDepend(contact_batch_load_fn)):
        return loader.load(self.name)

    friends: List[Friend] = []
    @mapper(lambda items: [Friend(name=item) for item in items])  # transform after data received
    def resolve_friends(self, loader=LoaderDepend(friends_batch_load_fn)):
        return loader.load(self.name)

class Root(BaseModel):
    users: List[User] = []
    def resolve_users(self):
        return [
          {"name": "tangkikodo", "age": 19},
            User(name="tangkikodo", age=19),  # transform first
            User(name='john', age=21),
            # User(name='trump', age=59),
            # User(name='sally', age=21),
            # User(name='some one', age=0)
        ]

async def main():
    import json
    root = await Resolver().resolve(Root())
    dct = root.dict()
    print(json.dumps(dct, indent=4))

asyncio.run(main())
```

**output**:

```json
{
  "users": [
    {
      "name": "tangkikodo",
      "age": 19,
      "greeting": "hello, i'm tangkikodo, 19 years old.",
      "contact": {
        "number": 900
      },
      "friends": [
        {
          "name": "tom",
          "contact": {
            "number": 100
          }
        },
        {
          "name": "jerry",
          "contact": {
            "number": 200
          }
        }
      ]
    },
    {
      "name": "john",
      "age": 21,
      "greeting": "hello, i'm john, 21 years old.",
      "contact": {
        "number": 1000
      },
      "friends": [
        {
          "name": "mike",
          "contact": {
            "number": 3000
          }
        },
        {
          "name": "wallace",
          "contact": {
            "number": 400
          }
        }
      ]
    }
  ]
}
```

- Full-feature [example](./examples/6_sqlalchemy_loaderdepend_global_filter.py) which includes `dataloader`, `LoaderDepend` and global `loader_filters`
- Helps you asynchoronously, resursively resolve a pydantic object (or dataclass object)
- When used in conjunction with aiodataloader, allows you to easily generate nested data structures without worrying about generating N+1 queries.
- say byebye to contextvars when using dataloader.
- Inspired by [GraphQL](https://graphql.org/) and [graphene](https://graphene-python.org/)

## Install

```shell
pip install pydantic-resolve

pip install "pydantic-resolve[dataloader]"  # install with aiodataloader, from v1.0, aiodataloader is a default dependency, [dataloader] is removed.
```

- use `resolve` for simple scenario,
- use `Resolver` and `LoaderDepend` for complicated nested batch query.

```python
from pydantic_resolve import (
    resolve,                     # handle simple resolving task
    Resolver, LoaderDepend,      # handle schema resolving with LoaderDepend and DataLoader
    ResolverTargetAttrNotFound, DataloaderDependCantBeResolved, LoaderFieldNotProvidedError
)
```

## Run FastAPI example

```shell
poetry shell
cd examples
uvicorn fastapi_demo.main:app
# http://localhost:8000/docs#/default/get_tasks_tasks_get
```

## Some documentations.

- [Reason](./doc/reason-en.md)
- [How LoaderDepend works](./doc/loader-en.md)
- [Comparsion with common solutions](./doc/compare-en.md)

For more examples, please explore [examples](./examples/) folder.

## Unittest

```shell
poetry run python -m unittest  # or
poetry run pytest  # or
poetry run tox
```

## Coverage

```shell
poetry run coverage run -m pytest
poetry run coverage report -m
```
