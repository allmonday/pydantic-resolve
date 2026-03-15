"""
测试用的实体定义
"""

from typing import Optional, List
from pydantic import BaseModel
from pydantic_resolve import base_entity, query, Relationship
from pydantic_resolve.utils.dataloader import build_list


# 创建测试用的 DataLoader
async def user_loader(user_ids: List[int]) -> List[dict]:
    """模拟用户加载器"""
    users = {
        1: {"id": 1, "name": "Alice", "email": "alice@example.com"},
        2: {"id": 2, "name": "Bob", "email": "bob@example.com"},
    }
    return build_list(
        [users.get(uid) for uid in user_ids],
        user_ids,
        lambda u: u["id"] if u else None
    )


async def post_loader(post_ids: List[int]) -> List[dict]:
    """模拟文章加载器"""
    posts = {
        1: {"id": 1, "title": "First Post", "author_id": 1},
        2: {"id": 2, "title": "Second Post", "author_id": 2},
    }
    return build_list(
        [posts.get(pid) for pid in post_ids],
        post_ids,
        lambda p: p["id"] if p else None
    )


async def comment_loader(comment_ids: List[int]) -> List[dict]:
    """模拟评论加载器"""
    comments = {
        1: {"id": 1, "text": "Great post!", "post_id": 1, "author_id": 2},
        2: {"id": 2, "text": "Thanks!", "post_id": 1, "author_id": 1},
    }
    return build_list(
        [comments.get(cid) for cid in comment_ids],
        comment_ids,
        lambda c: c["id"] if c else None
    )


# 定义 BaseEntity
BaseEntity = base_entity()


# 定义 UserEntity
class UserEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(field='id', target_kls=list['PostEntity'], loader=post_loader)
    ]
    id: int
    name: str
    email: str

    @query
    @staticmethod
    async def get_all(limit: int = 10) -> List['UserEntity']:
        """获取所有用户"""
        return [
            UserEntity(id=1, name="Alice", email="alice@example.com"),
            UserEntity(id=2, name="Bob", email="bob@example.com"),
        ][:limit]

    @query
    @staticmethod
    async def get_by_id(id: int) -> Optional['UserEntity']:
        """根据 ID 获取用户"""
        users = {
            1: UserEntity(id=1, name="Alice", email="alice@example.com"),
            2: UserEntity(id=2, name="Bob", email="bob@example.com"),
        }
        return users.get(id)


# 定义 CommentEntity
class CommentEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(field='author_id', target_kls=UserEntity, loader=user_loader),
    ]
    id: int
    text: str
    post_id: int
    author_id: int


# 定义 PostEntity
class PostEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(field='author_id', target_kls=UserEntity, loader=user_loader),
        Relationship(field='id', target_kls=list['CommentEntity'], loader=comment_loader)
    ]
    id: int
    title: str
    author_id: int

    @query
    @staticmethod
    async def get_all() -> List['PostEntity']:
        """获取所有文章"""
        return [
            PostEntity(id=1, title="First Post", author_id=1),
            PostEntity(id=2, title="Second Post", author_id=2),
        ]

    @query
    @staticmethod
    async def get_comments(post_id: int, limit: int = 10) -> List['CommentEntity']:
        """获取指定文章的评论（分页）- 测试跨实体返回类型"""
        comments = [
            CommentEntity(id=1, text="Great post!", post_id=1, author_id=2),
            CommentEntity(id=2, text="Thanks!", post_id=1, author_id=1),
        ]
        return [c for c in comments if c.post_id == post_id][:limit]
