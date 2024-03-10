import asyncio
from pydantic import BaseModel
from pydantic_resolve import Resolver

comments_table = [
    dict(id=1, blog_id=1, content='its interesting'),
    dict(id=2, blog_id=1, content='i need more example'),
    dict(id=3, blog_id=2, content='what problem does it solved?'),
    dict(id=4, blog_id=2, content='interesting')]

async def query_comments(blog_id: int):
    print(f'run query - {blog_id}')
    return [c for c in comments_table if c['blog_id'] == blog_id]

async def get_blogs():
    return [
        dict(id=1, title='what is pydantic-resolve'),
        dict(id=2, title='what is composition oriented development pattarn'),
    ]

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
    blogs: list[Blog] = []
    async def resolve_blogs(self):
        return await get_blogs()

    comment_count: int = 0
    def post_comment_count(self):
        return sum([b.comment_count for b in self.blogs])

async def single():
    blog = Blog(id=1, title='what is pydantic-resolve')
    blog = await Resolver().resolve(blog)
    print(blog)


async def batch():
    my_blog_site = MyBlogSite()
    my_blog_site = await Resolver().resolve(my_blog_site)
    print(my_blog_site.json(indent=2))


async def main():
    await single()
    await batch()

asyncio.run(main())
