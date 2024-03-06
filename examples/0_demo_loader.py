import asyncio
from pydantic import BaseModel
from pydantic_resolve import Resolver, build_list, LoaderDepend

comments_table = [
    dict(id=1, blog_id=1, content='its interesting'),
    dict(id=2, blog_id=1, content='i dont understand'),
    dict(id=3, blog_id=2, content='why? how?'),
    dict(id=4, blog_id=2, content='wow!'),
]

async def blog_to_comments_loader(blog_ids: list[int]):
    print(blog_ids)
    return build_list(comments_table, blog_ids, lambda c: c['blog_id'])

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

async def batch():
    my_blog_site = MyBlogSite()
    my_blog_site = await Resolver().resolve(my_blog_site)
    print(my_blog_site.json(indent=4))


async def main():
    await batch()

asyncio.run(main())
