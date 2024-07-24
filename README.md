[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![Downloads](https://static.pepy.tech/personalized-badge/pydantic-resolve?period=month&units=abbreviation&left_color=grey&right_color=orange&left_text=Downloads)](https://pepy.tech/project/pydantic-resolve)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
![Test Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/allmonday/6f1661c6310e1b31c9a10b0d09d52d11/raw/covbadge.json)
[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)

Pydantic-resolve is a schema based, hierarchical solution for fetching and crafting data.

Features:

0. The best data aggregration (bff) tool for FastAPI/Django ninja ever. 
1. By providing/describing your pydantic schema and instance(s), resolver will recursively resolve uncertain nodes and their descendants.
2. You can modify resolved nodes, or compute new nodes based on resolved nodes, no need of iteration.
3. Schemas are pluggable, easy to combine together and easy to reuse.


## Install

> User of pydantic v2, please use [pydantic2-resolve](https://github.com/allmonday/pydantic2-resolve) instead.

```shell
pip install pydantic-resolve
```


## Inherit and extend schemas, then resolve

```python
from __future__ import annotations

class Blog(BaseModel):
    id: int
    title: str

class Comment(BaseModel):
    id: int
    content: str

class MySite(BaseModel):
    blogs: list[MySiteBlog] = []
    async def resolve_blogs(self):
        return await bs.get_blogs()

    comment_count: int = 0
    def post_comment_count(self):
        return sum([b.comment_count for b in self.blogs])  # for total

class MySiteBlog(Blog):
    comments: list[Comment] = []
    def resolve_comments(self, loader=LoaderDepend(blog_to_comments_loader)):
        return loader.load(self.id)

    comment_count: int = 0
    def post_comment_count(self):
        return len(self.comments)  # for each blog
        
my_blog_site = MyBlogSite(name: "tangkikodo's blog")
my_blog_site = await Resolver().resolve(my_blog_site)
```

## Full demo with FastAPI & hey-api/openapi-ts

https://github.com/allmonday/pydantic-resolve-demo


## API Reference
for more details, please refer to: https://allmonday.github.io/pydantic-resolve/reference_api/

## Composition oriented development-pattern (wip)

This repo introduce a pattern that balance the speed of development and the maintaince, readability of your project, based on pydantic-resolve.

https://github.com/allmonday/composition-oriented-development-pattern


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


## Sponsor

If this code helps and you wish to support me

Paypal: https://www.paypal.me/tangkikodo


## Others
[Discord](https://discord.com/channels/1197929379951558797/1197929379951558800)
