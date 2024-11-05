Pydantic-resolve 使用声明的方式来描述数据, 可以从简到繁构造各种数据, 同时使其易于维护.

以 `MySite` 为例, 它包含了 blogs 和 comments 信息

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

## 描述 schemas

借助 annotations, 我们从上到下描述了 MySite 的结构

name, id, title 等是已知的字段, 之后会根据数据赋值

blogs, comments 等数据还是未知数, 所以赋了默认值

```python linenums="1" hl_lines="8 14"
from __future__ import annotations
import asyncio
from pydantic import BaseModel

class MySite(BaseModel):
    name: str

    blogs: list[Blog] = []

class Blog(BaseModel):
    id: int
    title: str

    comments: list[Comment] = []

class Comment(BaseModel):
    id: int
    content: str
```

## 添加 resolve 方法

resolve 方法描述了获取数据的具体方式

> resolve 方法支持异步调用

```python linenums="1" hl_lines="9-10 17-18"
from __future__ import annotations
from pydantic_resolve import Resolver
from pydantic import BaseModel

class MySite(BaseModel):
    name: str

    blogs: list[Blog] = []
    async def resolve_blogs(self):
        return await get_blogs()

class Blog(BaseModel):
    id: int
    title: str

    comments: list[Comment] = []
    async def resolve_comments(self):
        return await query_comments(self.id)

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

万事具备, 可以开始实例化 Resolver 来解析了

```python linenums="1"

async def main():
    my_blog_site = MySite(name: "tangkikodo's blog")
    my_blog_site = await Resolver().resolve(my_blog_site)
    print(my_blog_site.json(indent=2))
```

我们顺利获得了期望的数据

```shell linenums="1"
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
    }
  ],
}
```

你也许注意到了, `run-query` 被打印了两次, 在获取 comments 的时候发生了重复查询. (N+1 查询)

我们会在下一章节使用 dataloader 解决这个问题
