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


## For user from GraphQL

This is how we make queries in GraphQL, dive by describing schema and field names.

```gql
query {
    MyBlogSite {
        name
        blogs {
            id
            title
            comments {
                id
                content
            }
            # comment_count
        }
        # comment_count
    }
}
```

> using query statement is flexible, but for scenarios like `API integration` it can be difficult to maintain.

In client, field `comment_count` is the length of each blog and also the total count (just for demo, pls ignore pagination staff), so client side need to iterate over the blogs to get the length and the sum, which is boring (things getting worse if the structure is deeper).

With pydantic-resolve, we can handle these calculations at server side. Let see how it works.

By transforming the query into pydantic schemas and attach some resolve, post methods, it looks like:


```python
from __future__ import annotations
import comment_service as cs
import blog_service as bs

class MySite(BaseModel):
    blogs: list[MySiteBlog] = []
    async def resolve_blogs(self):
        return await bs.get_blogs()

    comment_count: int = 0
    def post_comment_count(self):
        return sum([b.comment_count for b in self.blogs])  # for total

class MySiteBlog(bs.Blog):  # >>> inherit and extend <<<
    comments: list[cs.Comment] = []
    def resolve_comments(self, loader=LoaderDepend(cs.blog_to_comments_loader)):
        return loader.load(self.id)

    comment_count: int = 0
    def post_comment_count(self):
        return len(self.comments)  # for each blog
        
async def main():
    my_blog_site = MyBlogSite(name: "tangkikodo's blog")
    my_blog_site = await Resolver().resolve(my_blog_site)
```

schemas , query functions and loader functions are provided by entity's service modules. 

And then we can simpily **inherit** and **extend** from these base schemas to declare the schemas you want.

> This just like columns of values (inherit) and of foreign keys (extend) in concept of relational database.

After transforming GraphQL query into pydantic schemas, post calculation become dead easy, and no more iterations.


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
