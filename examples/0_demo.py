import asyncio
from pydantic import BaseModel
from pydantic_resolve import Resolver

comments_table = [
    dict(id=1, blog_id=1, content='its interesting'),
    dict(id=2, blog_id=1, content='i dont understand'),
    dict(id=3, blog_id=2, content='why? how?'),
    dict(id=4, blog_id=2, content='wow!'),
]

async def query_comments(blog_id: int):
    print(f'run query - {blog_id}')
    return [c for c in comments_table if c['blog_id'] == blog_id]

class Comment(BaseModel):
    id: int
    content: str

class Blog(BaseModel):
    id: int
    title: str

    comments: list[Comment] = []
    async def resolve_comments(self):
        return await query_comments(self.id)

class MyBlogSite(BaseModel):
    blogs: list[Blog]


async def single():
    blog = Blog(id=1, title='what is pydantic-resolve')
    blog = await Resolver().resolve(blog)
    print(blog)


async def batch():
    my_blog_site = MyBlogSite(
        blogs = [
            Blog(id=1, title='what is pydantic-resolve'),
            Blog(id=2, title='what is composition oriented development pattarn'),
        ]
    )
    my_blog_site = await Resolver().resolve(my_blog_site)
    print(my_blog_site.json(indent=4))


async def main():
    await single()
    await batch()

asyncio.run(main())
