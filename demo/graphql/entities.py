"""
示例实体定义 - 用于 GraphQL 演示
"""

from typing import List, Optional
from pydantic import BaseModel
from pydantic_resolve import base_entity, query, Relationship
from pydantic_resolve.utils.dataloader import build_list


# 创建 DataLoader
async def user_loader(user_ids: List[int]) -> List[dict]:
    """用户批量加载器"""
    users_db = {
        1: {"id": 1, "name": "Alice", "email": "alice@example.com", "role": "admin"},
        2: {"id": 2, "name": "Bob", "email": "bob@example.com", "role": "user"},
        3: {"id": 3, "name": "Charlie", "email": "charlie@example.com", "role": "user"},
        4: {"id": 4, "name": "Diana", "email": "diana@example.com", "role": "admin"},
    }
    return build_list(
        [users_db.get(uid) for uid in user_ids],
        user_ids,
        lambda u: u["id"] if u else None
    )


async def post_loader(post_ids: List[int]) -> List[dict]:
    """文章批量加载器"""
    posts_db = {
        1: {"id": 1, "title": "First Post", "content": "Hello World!", "author_id": 1, "status": "published"},
        2: {"id": 2, "title": "Second Post", "content": "GraphQL is awesome", "author_id": 2, "status": "published"},
        3: {"id": 3, "title": "Third Post", "content": "Python tips", "author_id": 1, "status": "draft"},
        4: {"id": 4, "title": "Fourth Post", "content": "FastAPI tutorial", "author_id": 3, "status": "published"},
    }
    return build_list(
        [posts_db.get(pid) for pid in post_ids],
        post_ids,
        lambda p: p["id"] if p else None
    )


async def comment_loader(comment_ids: List[int]) -> List[dict]:
    """评论批量加载器"""
    comments_db = {
        1: {"id": 1, "text": "Great post!", "author_id": 2, "post_id": 1},
        2: {"id": 2, "text": "Thanks!", "author_id": 1, "post_id": 1},
        3: {"id": 3, "text": "Very helpful", "author_id": 3, "post_id": 2},
        4: {"id": 4, "text": "Nice tutorial", "author_id": 4, "post_id": 4},
    }
    return build_list(
        [comments_db.get(cid) for cid in comment_ids],
        comment_ids,
        lambda c: c["id"] if c else None
    )


# 创建 BaseEntity
BaseEntity = base_entity()


class UserMetaEntity(BaseModel):
    id: int = 0
    name: str = ''

# User 实体
class UserEntity(BaseModel, BaseEntity):
    """用户实体"""
    __relationships__ = [
        Relationship(field='id', target_kls=list['PostEntity'], loader=post_loader, load_many=True, default_field_name='myposts')
    ]
    id: int
    name: str
    email: str
    role: str
    something: dict = {'key': 'value'}
    meta: list[UserMetaEntity] = [UserMetaEntity()]

    @query(name='users')
    async def get_all(cls, limit: int = 10, offset: int = 0) -> List['UserEntity']:
        """获取所有用户（分页）"""
        all_users = [
            UserEntity(id=1, name="Alice", email="alice@example.com", role="admin"),
            UserEntity(id=2, name="Bob", email="bob@example.com", role="user"),
            UserEntity(id=3, name="Charlie", email="charlie@example.com", role="user"),
            UserEntity(id=4, name="Diana", email="diana@example.com", role="admin"),
        ]
        return all_users[offset:offset + limit]

    @query(name='user')
    async def get_by_id(cls, id: int) -> Optional['UserEntity']:
        """根据 ID 获取用户"""
        users = {
            1: UserEntity(id=1, name="Alice", email="alice@example.com", role="admin"),
            2: UserEntity(id=2, name="Bob", email="bob@example.com", role="user"),
            3: UserEntity(id=3, name="Charlie", email="charlie@example.com", role="user"),
            4: UserEntity(id=4, name="Diana", email="diana@example.com", role="admin"),
        }
        return users.get(id)

    @query(name='admins')
    async def get_admins(cls) -> List['UserEntity']:
        """获取所有管理员"""
        return [
            UserEntity(id=1, name="Alice", email="alice@example.com", role="admin"),
            UserEntity(id=4, name="Diana", email="diana@example.com", role="admin"),
        ]


# Post 实体
class PostEntity(BaseModel, BaseEntity):
    """文章实体"""
    __relationships__ = [
        Relationship(field='author_id', target_kls=UserEntity, loader=user_loader, default_field_name='author'),
        Relationship(field='id', target_kls=list['CommentEntity'], loader=comment_loader, load_many=True, default_field_name='comments')
    ]
    id: int
    title: str
    content: str
    author_id: int
    status: str

    @query(name='posts')
    async def get_all(cls, limit: int = 10, status: Optional[str] = None) -> List['PostEntity']:
        """获取所有文章（可按状态筛选）"""
        all_posts = [
            PostEntity(id=1, title="First Post", content="Hello World!", author_id=1, status="published"),
            PostEntity(id=2, title="Second Post", content="GraphQL is awesome", author_id=2, status="published"),
            PostEntity(id=3, title="Third Post", content="Python tips", author_id=1, status="draft"),
            PostEntity(id=4, title="Fourth Post", content="FastAPI tutorial", author_id=3, status="published"),
        ]
        if status:
            return [p for p in all_posts if p.status == status][:limit]
        return all_posts[:limit]

    @query(name='post')
    async def get_by_id(cls, id: int) -> Optional['PostEntity']:
        """根据 ID 获取文章"""
        posts = {
            1: PostEntity(id=1, title="First Post", content="Hello World!", author_id=1, status="published"),
            2: PostEntity(id=2, title="Second Post", content="GraphQL is awesome", author_id=2, status="published"),
            3: PostEntity(id=3, title="Third Post", content="Python tips", author_id=1, status="draft"),
            4: PostEntity(id=4, title="Fourth Post", content="FastAPI tutorial", author_id=3, status="published"),
        }
        return posts.get(id)


# Comment 实体
class CommentEntity(BaseModel, BaseEntity):
    """评论实体"""
    __relationships__ = [
        Relationship(field='author_id', target_kls=UserEntity, loader=user_loader, default_field_name='author'),
        Relationship(field='post_id', target_kls=PostEntity, loader=post_loader, default_field_name='post')
    ]
    id: int
    text: str
    author_id: int
    post_id: int

    @query(name='comments')
    async def get_all(cls) -> List['CommentEntity']:
        """获取所有评论"""
        return [
            CommentEntity(id=1, text="Great post!", author_id=2, post_id=1),
            CommentEntity(id=2, text="Thanks!", author_id=1, post_id=1),
            CommentEntity(id=3, text="Very helpful", author_id=3, post_id=2),
            CommentEntity(id=4, text="Nice tutorial", author_id=4, post_id=4),
        ]
