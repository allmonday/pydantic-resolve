import asyncio
import json
from typing import Optional
from pydantic import BaseModel
from pydantic_resolve import Resolver, build_object, build_list, LoaderDepend
from aiodataloader import DataLoader

# Schema/ Entity
class Comment(BaseModel):
    id: int
    content: str
    user_id: int

class Blog(BaseModel):
    id: int
    title: str
    content: str

class User(BaseModel):
    id: int
    name: str


# Loaders/ relationships
class CommentLoader(DataLoader):
    async def batch_load_fn(self, comment_ids):
        comments = [
            dict(id=1, content="world is beautiful", blog_id=1, user_id=1),
            dict(id=2, content="Mars is beautiful", blog_id=2, user_id=2),
            dict(id=3, content="I love Mars", blog_id=2, user_id=3),
        ]
        return build_list(comments, comment_ids, lambda c: c['blog_id'])

class UserLoader(DataLoader):
    async def batch_load_fn(self, user_ids):
        users = [ dict(id=1, name="Alice"), dict(id=2, name="Bob"), ]
        return build_object(users, user_ids, lambda u: u['id'])


# Compose schemas and dataloaders together
class CommentWithUser(Comment):
    user: Optional[User] = None
    def resolve_user(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.user_id)

class BlogWithComments(Blog):
    comments: list[CommentWithUser] = []
    def resolve_comments(self, loader=LoaderDepend(CommentLoader)):
        return loader.load(self.id)


# Run
async def main():
    raw_blogs =[
        dict(id=1, title="hello world", content="hello world detail"),
        dict(id=2, title="hello Mars", content="hello Mars detail"),
    ]
    blogs = await Resolver().resolve([BlogWithComments.parse_obj(b) for b in raw_blogs])
    print(json.dumps(blogs, indent=2, default=lambda o: o.dict()))

asyncio.run(main())