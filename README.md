# Pydantic-resolve

[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
![Test Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/allmonday/6f1661c6310e1b31c9a10b0d09d52d11/raw/covbadge.json)
[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![Downloads](https://static.pepy.tech/personalized-badge/pydantic-resolve?period=month&units=abbreviation&left_color=grey&right_color=orange&left_text=Downloads)](https://pepy.tech/project/pydantic-resolve)

> A small yet powerful package which can run resolvers to generate deep nested datasets.

[Change log](./changelog.md)

**example**:

```python
# prepare dataloader

import asyncio
from typing import List, Optional
from pydantic import BaseModel
from pydantic_resolve import Resolver, mapper, LoaderDepend

# define dataset and loader functions
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
        'tom': 1001, 'jerry': 1002, 'mike': 1003, 'wallace': 1004, 'sam': 1005,
        'jim': 1006, 'sindy': 1007, 'lydia': 1008, 'tangkikodo': 1009, 'john': 1010,
        'trump': 2011, 'sally': 2012,
    }
    result = []
    for name in names:
        n = mock_db.get(name, None)
        result.append({'number': n} if n else None)
    return result
```

```python
# define data schemas

class Contact(BaseModel):
    number: Optional[int]

class Friend(BaseModel):
    name: str

    contact: Optional[Contact] = None
    @mapper(Contact)                                          # 1. resolve dataloader and map return dict to Contact object
    def resolve_contact(self, contact_loader=LoaderDepend(contact_batch_load_fn)):
        return contact_loader.load(self.name)

    is_contact_10: bool = False
    def post_is_contact_10(self):                             # 3. after resolve_contact executed, do extra computation
        if self.contact:
            if str(self.contact.number).startswith('10'):
                self.is_contact_10 = True
        else:
            self.is_contact_10 = False

class User(BaseModel):
    name: str
    age: int

    greeting: str = ''
    async def resolve_greeting(self):
        await asyncio.sleep(1)
        return f"hello, i'm {self.name}, {self.age} years old."

    contact: Optional[Contact] = None
    @mapper(Contact)
    def resolve_contact(self, contact_loader=LoaderDepend(contact_batch_load_fn)):
        return contact_loader.load(self.name)

    friends: List[Friend] = []
    @mapper(lambda names: [Friend(name=name) for name in names])
    def resolve_friends(self, friend_loader=LoaderDepend(friends_batch_load_fn)):
        return friend_loader.load(self.name)

    friend_count: int = 0
    def post_friend_count(self):
        self.friend_count = len(self.friends)

class Root(BaseModel):
    users: List[User] = []
    @mapper(lambda items: [User(**item) for item in items])
    def resolve_users(self):
        return [
            {"name": "tangkikodo", "age": 19},
            {"name": "john", "age": 20},
            {"name": "trump", "age": 21},
            {"name": "sally", "age": 22},
            {"name": "no man", "age": 23},
        ]

```

```python
# resolve results

async def main():
    import json
    root = Root()
    root = await Resolver().resolve(root)                 # 4. run it
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
        "number": 1009
      },
      "friends": [
        {
          "name": "tom",
          "contact": {
            "number": 1001
          },
          "is_contact_10": true
        },
        {
          "name": "jerry",
          "contact": {
            "number": 1002
          },
          "is_contact_10": true
        }
      ],
      "friend_count": 2
    },
    {
      "name": "john",
      "age": 20,
      "greeting": "hello, i'm john, 20 years old.",
      "contact": {
        "number": 1010
      },
      "friends": [
        {
          "name": "mike",
          "contact": {
            "number": 1003
          },
          "is_contact_10": true
        },
        {
          "name": "wallace",
          "contact": {
            "number": 1004
          },
          "is_contact_10": true
        }
      ],
      "friend_count": 2
    },
    ...
    ,
    {
      "name": "no man",
      "age": 23,
      "greeting": "hello, i'm no man, 23 years old.",
      "contact": null,
      "friends": [],
      "friend_count": 0
    }
  ]
}
```

## Install

```shell
pip install pydantic-resolve
```

- use `resolve` for simple scenario,
- use `Resolver` and `LoaderDepend` for complicated nested batch query.

## API

`Resolver(loader_filters, loader_instances, ensure_type)`

- `loader_filters`

  provide extra query filters along with loader key.

  detail: `examples/6_sqlalchemy_loaderdepend_global_filter.py` L55, L59

- `loader_instances`

  provide pre-created loader instance, with can `prime` data into loader cache.

  detail: `tests/resolver/test_20_loader_instance.py`, L62, L63

- `ensure_type`

  if `True`, resolve method is restricted to be annotated.

  detail: `tests/resolver/test_13_check_wrong_type`

`LoaderDepend(loader_fn)`

- `loader_fn`: subclass of DataLoader or batch_load_fn. [detail](https://github.com/syrusakbary/aiodataloader#dataloaderbatch_load_fn-options)

  declare dataloader dependency, `pydantic-resolve` will take the care of lifecycle of dataloader.

`build_list(rows, keys, fn)` & `build_object(rows, keys, fn)`

- `rows`: query result
- `keys`: batch_load_fn:keys
- `fn`: define the way to get primary key

  helper function to generate return value required by `batch_load_fn`. read the code for details.

`mapper(param)`

- `param`: can be either a class of pydantic or dataclass, or a lambda.

  `pydantic-resolve` will trigger the fn in `mapper` after inner future is resolved. it exposes an interface to change return schema even from the same dataloader.
  if param is a class, it will try to automatically transform it.

`ensure_subset(base_class)`

- `base_class`: pydantic class

  it can raise exception if fields of decorated class has field not existed in `base_class`.

  detail: `tests/utils/test_2_ensure_subset.py`

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
