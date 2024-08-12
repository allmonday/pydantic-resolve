import asyncio
import json
from pydantic import BaseModel
from pydantic_resolve import Resolver

class Comment(BaseModel):
    id: int
    content: str

class Blog(BaseModel):
    id: int
    title: str
    content: str

    comments: list[Comment] = []
    def resolve_comments(self):
        return get_comments(self.id)


def get_blogs():
    return [
        dict(id=1, title="hello world", content="hello world detail"),
        dict(id=2, title="hello Mars", content="hello Mars detail"),
    ]

def get_comments(id):
    comments = [
        dict(id=1, content="world is beautiful", blog_id=1),
        dict(id=2, content="Mars is beautiful", blog_id=2),
        dict(id=3, content="I love Mars", blog_id=2),
    ]
    return [c for c in comments if c['blog_id'] == id]


async def main():
    blogs = [Blog.parse_obj(blog) for blog in get_blogs()]
    blogs = await Resolver().resolve(blogs)
    print(json.dumps(blogs, indent=2, default=lambda o: o.dict()))

asyncio.run(main())