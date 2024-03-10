# Dataloader

quote from [aiodataloader](https://github.com/syrusakbary/aiodataloader)

> DataLoader is a generic utility to be used as part of your application's data fetching layer to provide a simplified and consistent API over various remote data sources such as databases or web services via batching and caching.

In this phase, we'll fix the `N+1` query with the help of dataloader.

1. import LoaderDepend (it isolate the type info)
2. change query_comments to a loader function
3. declare loader in resolve_comments

> In pydantic-resolve, you can decleare and use dataloader in anywhere, without worring about the mess of context which happens in graphql

```python linenums="1" hl_lines="3 15-18 32-33"
import asyncio
from pydantic import BaseModel
from pydantic_resolve import Resolver, build_list, LoaderDepend

blogs_table = [
    dict(id=1, title='what is pydantic-resolve'),
    dict(id=2, title='what is composition oriented development pattarn')]

comments_table = [
    dict(id=1, blog_id=1, content='its interesting'),
    dict(id=2, blog_id=1, content='i need more example'),
    dict(id=3, blog_id=2, content='what problem does it solved?'),
    dict(id=4, blog_id=2, content='interesting')]

async def blog_to_comments_loader(blog_ids: list[int]):
    print(blog_ids)
    # group the searched comments by blog_id.
    return build_list(comments_table, blog_ids, lambda c: c['blog_id'])

async def get_blogs():
    return blogs_table

class Comment(BaseModel):
    id: int
    content: str

class Blog(BaseModel):
    id: int
    title: str

    comments: list[Comment] = []
    def resolve_comments(self, loader=LoaderDepend(blog_to_comments_loader)):
        return loader.load(self.id)
    
    comment_count: int = 0
    def post_comment_count(self):
        return len(self.comments)


class MyBlogSite(BaseModel):
    blogs: list[Blog] = []
    async def resolve_blogs(self):
        return await get_blogs()

    comment_count: int = 0
    def post_comment_count(self):
        return sum([b.comment_count for b in self.blogs])

async def main():
    my_blog_site = MyBlogSite()
    my_blog_site = await Resolver().resolve(my_blog_site)
    print(my_blog_site.json(indent=4))

asyncio.run(main())
```

check the output of `blog_to_comments_loader`, it only triggered once.

```shell
[1, 2]
```