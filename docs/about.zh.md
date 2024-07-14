# Welcome to Pydantic-resolve

Pydantic-resolve is a hierarchical solution focus on data fetching and processing, from simple to complicated.

For example, we want to build a view data named `MySite` which is required by a blog site page, it not only contains blogs, and it's comments, but also can calculate **total comments count of both blog level and site level**.

Let's describe it in form of graphql query for clarity.

```graphql linenums="1"
query {
    MySite {
        name
        blogs {
            id
            title
            comments {
                id
                content
            }
            # comment_count  # comments count for blog
        }
        # comment_count  # total comments
    }
}
```
Our source data of blogs and comments are prepared.

```python linenums="1"
blogs_table = [
    dict(id=1, title='what is pydantic-resolve'),
    dict(id=2, title='what is composition oriented development pattarn')]

comments_table = [
    dict(id=1, blog_id=1, content='its interesting'),
    dict(id=2, blog_id=1, content='i need more example'),
    dict(id=3, blog_id=2, content='what problem does it solved?'),
    dict(id=4, blog_id=2, content='interesting')]
```

Assuming `comment_count` is a extra field (length of comment), which is required and calculated by client after fetching the data.

> @property on @computed (in pydantic v2) can also works, just post_ method provides more context related params

So that client side need to iterate over the blogs to get the length and the sum, which is boring (things gets worse if the structure is deeper).

In pydantic-resolve, we handle this process at schema side.

## Describe by pydantic schemas:

```python linenums="1" hl_lines="8 9 15 16"
from __future__ import annotations 
import asyncio
from pydantic import BaseModel

class MySite(BaseModel):
    name: str

    blogs: list[Blog] = []
    comment_count: int = 0

class Blog(BaseModel):
    id: int
    title: str

    comments: list[Comment] = []
    comment_count: int = 0

class Comment(BaseModel):
    id: int
    content: str
```

We leave unresolved fields with default value to make it able to be loaded by pydantic.

## Attach resolve and post

And then add some `resolve` & `post` methods, for example `resolve_comments` will fetch data and then assigned it to `comments` field.

- **resolve**: it will run your query function to fetch children and descendants
- **post**: after descendant fields are all resolved, post will be called to calculate comment count.

```python linenums="1" hl_lines="9-10 13-15 22-23 26-27"
from __future__ import annotations 
from pydantic_resolve import Resolver
from pydantic import BaseModel

class MySite(BaseModel):
    name: str

    blogs: list[Blog] = []
    async def resolve_blogs(self):
        return await get_blogs()

    comment_count: int = 0
    def post_comment_count(self):
        # >> it will wait until all blogs are resolved
        return sum([b.comment_count for b in self.blogs])

class Blog(BaseModel):
    id: int
    title: str

    comments: list[Comment] = []
    async def resolve_comments(self):
        return await query_comments(self.id)

    comment_count: int = 0
    def post_comment_count(self):
        return len(self.comments)

class Comment(BaseModel):
    id: int
    content: str



async def query_comments(blog_id: int):
    print(f'run query - {blog_id}')
    return [c for c in comments_table if c['blog_id'] == blog_id]

async def get_blogs():
    return blogs_table
```

## Resolver

let's start and check the output.

```python linenums="1" hl_lines="2 3"

async def main():
    my_blog_site = MySite(name: "tangkikodo's blog")
    my_blog_site = await Resolver().resolve(my_blog_site)
    print(my_blog_site.json(indent=2))
```


```shell linenums="1" hl_lines="19 34 37"
run-query - 1
run-query - 2

{
  "blogs": [
    {
      "id": 1,
      "title": "what is pydantic-resolve",
      "comments": [
        {
          "id": 1,
          "content": "its interesting"
        },
        {
          "id": 2,
          "content": "i need more example"
        }
      ],
      "comment_count": 2
    },
    {
      "id": 2,
      "title": "what is composition oriented development pattarn",
      "comments": [
        {
          "id": 3,
          "content": "what problem does it solved?"
        },
        {
          "id": 4,
          "content": "interesting"
        }
      ],
      "comment_count": 2
    }
  ],
  "comment_count": 4
}
```

We have fetched and tweaked the view data we want, but wait, there is a problem

Let's have a look of the info printed from `query_comments`, **it was called by twice!**

This is a typical N+1 query which will have performance issue if we have a big number of blogs.

Let's fix it in next phase.
