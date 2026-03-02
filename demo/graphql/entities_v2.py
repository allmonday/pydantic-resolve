"""
V2 实体定义 - 使用 QueryConfig/MutationConfig 配置化方式

与 entities.py 的区别：
- 不继承 BaseEntity，只继承 BaseModel
- 关系定义从类内部移到外部的 ErDiagram
- Query/Mutation 方法通过 QueryConfig/MutationConfig 配置，而非装饰器
"""

from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from pydantic_resolve import (
    Relationship, ErDiagram, Entity,
    QueryConfig, MutationConfig, config_global_resolver
)
from pydantic_resolve.utils.dataloader import build_list, build_object


# =====================================
# Enum Types
# =====================================

class UserRole(str, Enum):
    """用户角色枚举"""
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


class PostStatus(str, Enum):
    """文章状态枚举"""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# =====================================
# Input Types for Mutations
# =====================================

class CreateUserInput(BaseModel):
    """创建用户的输入类型"""
    name: str = Field(description="用户名称")
    email: str = Field(description="邮箱地址")
    role: UserRole = Field(default=UserRole.USER, description="用户角色")


class CreatePostInput(BaseModel):
    """创建文章的输入类型"""
    title: str = Field(description="文章标题")
    content: str = Field(description="文章内容")
    author_id: int = Field(description="作者ID")
    status: PostStatus = Field(default=PostStatus.DRAFT, description="文章状态")


# 模拟数据库（在类定义后初始化）
users_db_v2: Dict[int, 'UserEntityV2'] = {}
posts_db_v2: Dict[int, 'PostEntityV2'] = {}
comments_db_v2: Dict[int, 'CommentEntityV2'] = {}
user_id_counter_v2 = 0
post_id_counter_v2 = 0
comment_id_counter_v2 = 0


# =====================================
# 实体类定义（不继承 BaseEntity，不含 @query/@mutation）
# =====================================

class CommentEntityV2(BaseModel):
    """评论实体 V2 - 不继承 BaseEntity

    表示用户对文章的评论内容。
    """
    id: int = Field(description="评论ID")
    text: str = Field(description="评论内容")
    author_id: int = Field(description="评论者用户ID")
    post_id: int = Field(description="被评论的文章ID")


class PostEntityV2(BaseModel):
    """文章实体 V2 - 不继承 BaseEntity

    表示用户发布的文章内容，包含标题、内容和作者信息。
    """
    id: int = Field(description="文章ID")
    title: str = Field(description="文章标题")
    content: str = Field(default="", description="文章内容")
    author_id: int = Field(description="作者用户ID")
    status: PostStatus = Field(description="文章状态")


class UserEntityV2(BaseModel):
    """用户实体 V2 - 不继承 BaseEntity

    表示系统中的用户信息，包括基本资料和关联的文章数据。
    """
    id: int = Field(description="用户唯一标识ID")
    name: str = Field(description="用户姓名")
    email: str = Field(description="用户邮箱地址")
    role: UserRole = Field(description="用户角色")


# =====================================
# DataLoader 定义（在所有实体类定义之后）
# =====================================

async def user_loader_v2(user_ids: List[int]) -> List[dict]:
    """用户批量加载器 - 从全局数据库读取"""
    users = [u if u else None for u in [users_db_v2.get(uid) for uid in user_ids]]
    return list(build_object(users, user_ids, lambda u: u.id if u else None))


async def post_loader_v2(post_ids: List[int]) -> List[dict]:
    """文章批量加载器 - 从全局数据库读取"""
    posts = [p if p else None for p in [posts_db_v2.get(pid) for pid in post_ids]]
    return list(build_object(posts, post_ids, lambda p: p.id if p else None))


async def user_posts_loader_v2(user_ids: List[int]) -> List[List[dict]]:
    """Load posts by author IDs - for UserEntityV2.myposts relationship"""
    all_posts = [p for p in posts_db_v2.values()]
    return list(build_list(all_posts, user_ids, lambda p: p.author_id))


async def post_comments_loader_v2(post_ids: List[int]) -> List[List[dict]]:
    """Load comments by post IDs - for PostEntityV2.comments relationship"""
    all_comments = [c for c in comments_db_v2.values()]
    return list(build_list(all_comments, post_ids, lambda c: c.post_id))


# =====================================
# Query 方法定义（外部函数，无需 cls 参数）
# =====================================

async def get_all_comments() -> List[CommentEntityV2]:
    """获取所有评论"""
    return list(comments_db_v2.values())


async def get_all_posts(limit: int = 10, status: Optional[PostStatus] = None) -> List[PostEntityV2]:
    """获取所有文章（可按状态筛选）"""
    all_posts = list(posts_db_v2.values())
    if status:
        return [p for p in all_posts if p.status == status][:limit]
    return all_posts[:limit]


async def get_post_by_id(id: int) -> Optional[PostEntityV2]:
    """根据 ID 获取文章"""
    return posts_db_v2.get(id)


async def get_all_users(limit: int = 10, offset: int = 0) -> List[UserEntityV2]:
    """获取所有用户（分页）"""
    all_users = list(users_db_v2.values())
    return all_users[offset:offset + limit]


async def get_user_by_id(id: int) -> Optional[UserEntityV2]:
    """根据 ID 获取用户"""
    return users_db_v2.get(id)


# =====================================
# Mutation 方法定义（外部函数，无需 cls 参数）
# =====================================

async def create_comment(text: str, author_id: int, post_id: int) -> CommentEntityV2:
    """创建新评论并返回创建的评论对象"""
    global comment_id_counter_v2
    comment_id_counter_v2 += 1
    new_comment = CommentEntityV2(
        id=comment_id_counter_v2,
        text=text,
        author_id=author_id,
        post_id=post_id
    )
    comments_db_v2[comment_id_counter_v2] = new_comment
    return new_comment


async def create_post(title: str, content: str, author_id: int, status: PostStatus = PostStatus.DRAFT) -> PostEntityV2:
    """创建新文章并返回创建的文章对象"""
    global post_id_counter_v2
    post_id_counter_v2 += 1
    new_post = PostEntityV2(
        id=post_id_counter_v2,
        title=title,
        content=content,
        author_id=author_id,
        status=status
    )
    posts_db_v2[post_id_counter_v2] = new_post
    return new_post


async def create_post_with_input(input: CreatePostInput) -> PostEntityV2:
    """使用 Input Type 创建新文章"""
    global post_id_counter_v2
    post_id_counter_v2 += 1
    new_post = PostEntityV2(
        id=post_id_counter_v2,
        title=input.title,
        content=input.content,
        author_id=input.author_id,
        status=input.status
    )
    posts_db_v2[post_id_counter_v2] = new_post
    return new_post


async def create_user(name: str, email: str, role: UserRole = UserRole.USER) -> UserEntityV2:
    """创建新用户并返回创建的用户对象"""
    global user_id_counter_v2
    user_id_counter_v2 += 1
    new_user = UserEntityV2(
        id=user_id_counter_v2,
        name=name,
        email=email,
        role=role
    )
    users_db_v2[user_id_counter_v2] = new_user
    return new_user


async def create_user_with_input(input: CreateUserInput) -> UserEntityV2:
    """使用 Input Type 创建新用户"""
    global user_id_counter_v2
    user_id_counter_v2 += 1
    new_user = UserEntityV2(
        id=user_id_counter_v2,
        name=input.name,
        email=input.email,
        role=input.role
    )
    users_db_v2[user_id_counter_v2] = new_user
    return new_user


# =====================================
# 手动创建 ErDiagram（关系定义 + QueryConfig/MutationConfig）
# =====================================

diagram_v2 = ErDiagram(configs=[
    Entity(
        kls=UserEntityV2,
        relationships=[
            Relationship(field='id', target_kls=list[PostEntityV2],
                         loader=user_posts_loader_v2, default_field_name='myposts')
        ],
        queries=[
            QueryConfig(method=get_all_users, name='users_v2', description='获取所有用户（分页）'),
            QueryConfig(method=get_user_by_id, name='user_v2', description='根据 ID 获取用户'),
        ],
        mutations=[
            MutationConfig(method=create_user, name='createUserV2', description='创建新用户'),
            MutationConfig(method=create_user_with_input, name='createUserWithInputV2', description='使用 Input Type 创建新用户'),
        ]
    ),
    Entity(
        kls=PostEntityV2,
        relationships=[
            Relationship(field='author_id', target_kls=UserEntityV2,
                         loader=user_loader_v2, default_field_name='author'),
            Relationship(field='id', target_kls=list[CommentEntityV2],
                         loader=post_comments_loader_v2, default_field_name='comments')
        ],
        queries=[
            QueryConfig(method=get_all_posts, name='posts_v2', description='获取所有文章（可按状态筛选）'),
            QueryConfig(method=get_post_by_id, name='post_v2', description='根据 ID 获取文章'),
        ],
        mutations=[
            MutationConfig(method=create_post, name='createPostV2', description='创建新文章'),
            MutationConfig(method=create_post_with_input, name='createPostWithInputV2', description='使用 Input Type 创建新文章'),
        ]
    ),
    Entity(
        kls=CommentEntityV2,
        relationships=[
            Relationship(field='author_id', target_kls=UserEntityV2,
                         loader=user_loader_v2, default_field_name='author'),
            Relationship(field='post_id', target_kls=PostEntityV2,
                         loader=post_loader_v2, default_field_name='post')
        ],
        queries=[
            QueryConfig(method=get_all_comments, name='comments_v2', description='获取所有评论'),
        ],
        mutations=[
            MutationConfig(method=create_comment, name='createCommentV2', description='创建新评论'),
        ]
    ),
])


# =====================================
# 初始化模拟数据库
# =====================================

def init_db_v2():
    """初始化 V2 模拟数据库"""
    global users_db_v2, posts_db_v2, comments_db_v2
    global user_id_counter_v2, post_id_counter_v2, comment_id_counter_v2

    user_id_counter_v2 = 4
    post_id_counter_v2 = 4
    comment_id_counter_v2 = 4

    users_db_v2 = {
        1: UserEntityV2(id=1, name="Alice", email="alice@example.com", role=UserRole.ADMIN),
        2: UserEntityV2(id=2, name="Bob", email="bob@example.com", role=UserRole.USER),
        3: UserEntityV2(id=3, name="Charlie", email="charlie@example.com", role=UserRole.USER),
        4: UserEntityV2(id=4, name="Diana", email="diana@example.com", role=UserRole.ADMIN),
    }

    posts_db_v2 = {
        1: PostEntityV2(id=1, title="First Post", content="Hello World!", author_id=1, status=PostStatus.PUBLISHED),
        2: PostEntityV2(id=2, title="Second Post", content="GraphQL is awesome", author_id=2, status=PostStatus.PUBLISHED),
        3: PostEntityV2(id=3, title="Third Post", content="Python tips", author_id=1, status=PostStatus.DRAFT),
        4: PostEntityV2(id=4, title="Fourth Post", content="FastAPI tutorial", author_id=3, status=PostStatus.PUBLISHED),
    }

    comments_db_v2 = {
        1: CommentEntityV2(id=1, text="Great post!", author_id=2, post_id=1),
        2: CommentEntityV2(id=2, text="Thanks!", author_id=1, post_id=1),
        3: CommentEntityV2(id=3, text="Very helpful", author_id=3, post_id=2),
        4: CommentEntityV2(id=4, text="Nice tutorial", author_id=4, post_id=4),
    }


# 自动初始化
init_db_v2()

# 配置全局 Resolver（用于关系解析）
config_global_resolver(diagram_v2)
