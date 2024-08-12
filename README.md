[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![Downloads](https://static.pepy.tech/personalized-badge/pydantic-resolve?period=month&units=abbreviation&left_color=grey&right_color=orange&left_text=Downloads)](https://pepy.tech/project/pydantic-resolve)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
![Test Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/allmonday/6f1661c6310e1b31c9a10b0d09d52d11/raw/covbadge.json)
[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)

Pydantic-resolve is a schema based, hierarchical solution for data fetching and crafting.

**Features**:

1. with pydantic schema and instances, resolver recursively resolve uncertain nodes and their descendants.
2. nodes could be modified during post-process
3. plugable, easy to combine together and reuse.


## Install

> User of pydantic v2, please use [pydantic2-resolve](https://github.com/allmonday/pydantic2-resolve) instead.

```shell
pip install pydantic-resolve
```


## Hello world

build blogs with comments

```python
import asyncio
import json
from pydantic import BaseModel
from pydantic_resolve import Resolver

class Comment(BaseModel):
    id: int
    content: str

class Blog(BaseModel):
    id: int
    title: str
    content: str

    comments: list[Comment] = []
    def resolve_comments(self):
        return get_comments(self.id)


def get_blogs():
    return [
        dict(id=1, title="hello world", content="hello world detail"),
        dict(id=2, title="hello Mars", content="hello Mars detail"),
    ]

def get_comments(id):
    comments = [
        dict(id=1, content="world is beautiful", blog_id=1),
        dict(id=2, content="Mars is beautiful", blog_id=2),
        dict(id=3, content="I love Mars", blog_id=2),
    ]
    return [c for c in comments if c['blog_id'] == id]


async def main():
    blogs = [Blog.parse_obj(blog) for blog in get_blogs()]
    blogs = await Resolver().resolve(blogs)
    print(json.dumps(blogs, indent=2, default=lambda o: o.dict()))

asyncio.run(main())
```

```json
[
  {
    "id": 1,
    "title": "hello world",
    "content": "hello world detail",
    "comments": [
      {
        "id": 1,
        "content": "world is beautiful"
      }
    ]
  },
  {
    "id": 2,
    "title": "hello Mars",
    "content": "hello Mars detail",
    "comments": [
      {
        "id": 2,
        "content": "Mars is beautiful"
      },
      {
        "id": 3,
        "content": "I love Mars"
      }
    ]
  }
]
```

## Documents

- **Quick start**: https://allmonday.github.io/pydantic-resolve/about/
- **API**: https://allmonday.github.io/pydantic-resolve/reference_api/
- **Demo**: https://github.com/allmonday/pydantic-resolve-demo
- **Composition oriented pattern**: https://github.com/allmonday/composition-oriented-development-pattern


## Sponsor

If this code helps and you wish to support me

Paypal: https://www.paypal.me/tangkikodo


## Discussion
[Discord](https://discord.com/channels/1197929379951558797/1197929379951558800)
