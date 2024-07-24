# Dataloader

什么是 [aiodataloader](https://github.com/syrusakbary/aiodataloader)

> DataLoader is a generic utility to be used as part of your application's data fetching layer to provide a simplified and consistent API over various remote data sources such as databases or web services via batching and caching.

为了解决重复查询的问题, 我们需要对代码做一些改动

1. 改造 query_comments 方法, 名为 `blog_to_comments_loader`, 接收 `blog_ids` 为参数
2. 使用 LoaderDepends 包装, 它会复杂 loader 的实例化

```python linenums="1" hl_lines="16 34"
from __future__ import annotations
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

class MyBlogSite(BaseModel):
    blogs: list[Blog] = []
    async def resolve_blogs(self):
        return await get_blogs()

class Blog(BaseModel):
    id: int
    title: str

    comments: list[Comment] = []
    def resolve_comments(self, loader=LoaderDepend(blog_to_comments_loader)):
        return loader.load(self.id)

class Comment(BaseModel):
    id: int
    content: str


async def main():
    my_blog_site = MyBlogSite()
    my_blog_site = await Resolver().resolve(my_blog_site)
    print(my_blog_site.json(indent=4))

asyncio.run(main())
```

这样一番改造之后, comments 的查询就便成了一个 batch 查询, 查询次数于是减少为一次

```shell
[1, 2]
```