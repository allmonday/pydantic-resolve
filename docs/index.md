# Welcome to Pydantic-resolve

pydantic-resolve is a hierarchical solution focus on data fetching and processing.

For example, we want to build a view data named `MyBlogSite` which is required by a blog site page, it contains blogs, and it's comments, we also want to calculate **total comments count of both blog level and site level**.

Our source data of blogs and comments are prepared

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

Let's describe it in form of graphql query for clarity.
> btw, reverse aggregation / filtering is a challenge in graphql, maybe you'll need the help of graphql-lodash

```graphql linenums="1"
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
            comment_count  # comments count for blog
        }
        comment_count  # total comments
    }
}
```

First, we can easily transform that into pydantic, so that the output schema will meet our requirement.

> use default value if this field is unknown on initialization.

```python linenums="1" hl_lines="12 13 18 19"
import asyncio
from pydantic import BaseModel

class Comment(BaseModel):
    id: int
    content: str

class Blog(BaseModel):
    id: int
    title: str

    comments: list[Comment] = []
    comment_count: int = 0

class MyBlogSite(BaseModel):
    name: str

    blogs: list[Blog] = []
    comment_count: int = 0
```

And then add some `resolve` & `post` methods, for example `resolve_comments` will fetch data and then assigned it to `comments` field.

- **resolve**: it will run your query function to fetch data of children
- **post**: after descendant fields are all resolved, post will be called to calculate comment count.

```python linenums="1" hl_lines="10-11 14-15 22-23 26-28"
class Comment(BaseModel):
    id: int
    content: str

class Blog(BaseModel):
    id: int
    title: str

    comments: list[Comment] = []
    async def resolve_comments(self):
        return await query_comments(self.id)

    comment_count: int = 0
    def post_comment_count(self):
        return len(self.comments)


class MyBlogSite(BaseModel):
    name: str

    blogs: list[Blog] = []
    async def resolve_blogs(self):
        return await get_blogs()

    comment_count: int = 0
    def post_comment_count(self):
        # >> it will wait until all blogs are resolved
        return sum([b.comment_count for b in self.blogs])

async def query_comments(blog_id: int):
    print(f'run query - {blog_id}')
    return [c for c in comments_table if c['blog_id'] == blog_id]

async def get_blogs():
    return blogs_table
```

let's start and check the output.

```python linenums="1" hl_lines="2 3"

async def main():
    my_blog_site = MyBlogSite(name: "tangkikodo's blog")
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

We have fetched and tweaked the view data we want, but wait, there still has a problem, let's have a look of the printed info from `query_comments`, it was called by twice!

This is a typical N+1 query which will have performance issue if we have a big number of blogs.

Let's fix it in next phase.
