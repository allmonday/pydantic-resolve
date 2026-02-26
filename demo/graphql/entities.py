"""
示例实体定义 - 用于 GraphQL 演示
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from pydantic_resolve import base_entity, query, mutation, Relationship


# =====================================
# Input Types for Mutations
# =====================================

class CreateUserInput(BaseModel):
    """创建用户的输入类型"""
    name: str = Field(description="用户名称")
    email: str = Field(description="邮箱地址")
    role: str = Field(default="user", description="用户角色")


class CreatePostInput(BaseModel):
    """创建文章的输入类型"""
    title: str = Field(description="文章标题")
    content: str = Field(description="文章内容")
    author_id: int = Field(description="作者ID")
    status: str = Field(default="draft", description="文章状态")


class UpdateUserInput(BaseModel):
    """更新用户的输入类型"""
    name: Optional[str] = Field(default=None, description="用户名称")
    email: Optional[str] = Field(default=None, description="邮箱地址")
    role: Optional[str] = Field(default=None, description="用户角色")


class UpdatePostInput(BaseModel):
    """更新文章的输入类型"""
    title: Optional[str] = Field(default=None, description="文章标题")
    content: Optional[str] = Field(default=None, description="文章内容")
    status: Optional[str] = Field(default=None, description="文章状态")


# 模拟数据库（在类定义后初始化）
users_db: Dict[int, 'UserEntity'] = {}
posts_db: Dict[int, 'PostEntity'] = {}
comments_db: Dict[int, 'CommentEntity'] = {}
user_id_counter = 4
post_id_counter = 4
comment_id_counter = 4


# 创建 DataLoader
async def user_loader(user_ids: List[int]) -> List[dict]:
    """用户批量加载器 - 从全局数据库读取"""
    users = [users_db.get(uid) for uid in user_ids]
    return [
        u.model_dump() if u else None
        for u in users
    ]


async def post_loader(post_ids: List[int]) -> List[dict]:
    """文章批量加载器 - 从全局数据库读取"""
    posts = [posts_db.get(pid) for pid in post_ids]
    return [
        p.model_dump() if p else None
        for p in posts
    ]


async def user_posts_loader(user_ids: List[int]) -> List[List[dict]]:
    """Load posts by author IDs - for UserEntity.myposts relationship"""
    # Group posts by author_id
    posts_by_author: Dict[int, List] = {}
    for post in posts_db.values():
        author_id = post.author_id
        if author_id not in posts_by_author:
            posts_by_author[author_id] = []
        posts_by_author[author_id].append(post.model_dump())

    # Return list of posts for each user_id
    return [posts_by_author.get(uid, []) for uid in user_ids]


async def comment_loader(comment_ids: List[int]) -> List[dict]:
    """评论批量加载器 - 从全局数据库读取"""
    comments = [comments_db.get(cid) for cid in comment_ids]
    return [
        c.model_dump() if c else None
        for c in comments
    ]


async def post_comments_loader(post_ids: List[int]) -> List[List[dict]]:
    """Load comments by post IDs - for PostEntity.comments relationship"""
    # Group comments by post_id
    comments_by_post: Dict[int, List] = {}
    for comment in comments_db.values():
        post_id = comment.post_id
        if post_id not in comments_by_post:
            comments_by_post[post_id] = []
        comments_by_post[post_id].append(comment.model_dump())

    # Return list of comments for each post_id
    return [comments_by_post.get(pid, []) for pid in post_ids]


# 创建 BaseEntity
BaseEntity = base_entity()


class UserMetaEntity(BaseModel):
    """用户元信息实体"""
    id: int = Field(default=0, description="元信息ID")
    name: str = Field(default="", description="元信息名称")

# User 实体
class UserEntity(BaseModel, BaseEntity):
    """用户实体

    表示系统中的用户信息，包括基本资料和关联的文章数据。
    """
    __relationships__ = [
        Relationship(field='id', target_kls=list['PostEntity'], loader=user_posts_loader, default_field_name='myposts')
    ]
    id: int = Field(description="用户唯一标识ID")
    name: str = Field(description="用户姓名", example="Alice")
    email: str = Field(description="用户邮箱地址")
    role: str = Field(description="用户角色（admin/user）")
    something: dict = Field(default={'key': 'value'}, description="额外信息字典")
    meta: list[UserMetaEntity] = Field(default_factory=list, description="用户元信息列表")

    @query(name='users')
    async def get_all(cls, limit: int = 10, offset: int = 0) -> List['UserEntity']:
        """获取所有用户（分页）"""
        all_users = list(users_db.values())
        return all_users[offset:offset + limit]

    @query(name='user')
    async def get_by_id(cls, id: int) -> Optional['UserEntity']:
        """根据 ID 获取用户"""
        return users_db.get(id)

    @query(name='admins')
    async def get_admins(cls) -> List['UserEntity']:
        """获取所有管理员"""
        return [u for u in users_db.values() if u.role == 'admin']

    @mutation(name='createUser', description='创建新用户')
    async def create_user(cls, name: str, email: str, role: str = 'user') -> 'UserEntity':
        """创建新用户并返回创建的用户对象"""
        global user_id_counter
        user_id_counter += 1
        new_user = UserEntity(
            id=user_id_counter,
            name=name,
            email=email,
            role=role
        )
        users_db[user_id_counter] = new_user
        return new_user

    @mutation(name='updateUser')
    async def update_user(cls, id: int, name: Optional[str] = None, email: Optional[str] = None) -> Optional['UserEntity']:
        """更新用户信息"""
        if id in users_db:
            user = users_db[id]
            if name is not None:
                user.name = name
            if email is not None:
                user.email = email
            return user
        return None

    @mutation(name='deleteUser')
    async def delete_user(cls, id: int) -> bool:
        """删除用户，返回是否成功"""
        if id in users_db:
            del users_db[id]
            return True
        return False

    @mutation(name='createUserWithInput', description='使用 Input Type 创建新用户')
    async def create_user_with_input(cls, input: CreateUserInput) -> 'UserEntity':
        """使用 Input Type 创建新用户"""
        global user_id_counter
        user_id_counter += 1
        new_user = UserEntity(
            id=user_id_counter,
            name=input.name,
            email=input.email,
            role=input.role
        )
        users_db[user_id_counter] = new_user
        return new_user

    @mutation(name='updateUserWithInput', description='使用 Input Type 更新用户')
    async def update_user_with_input(cls, id: int, input: UpdateUserInput) -> Optional['UserEntity']:
        """使用 Input Type 更新用户信息"""
        if id in users_db:
            user = users_db[id]
            if input.name is not None:
                user.name = input.name
            if input.email is not None:
                user.email = input.email
            if input.role is not None:
                user.role = input.role
            return user
        return None


# Post 实体
class PostEntity(BaseModel, BaseEntity):
    """文章实体

    表示用户发布的文章内容，包含标题、内容和作者信息。
    """
    __relationships__ = [
        Relationship(field='author_id', target_kls=UserEntity, loader=user_loader, default_field_name='author'),
        Relationship(field='id', target_kls=list['CommentEntity'], loader=post_comments_loader, default_field_name='comments')
    ]
    id: int = Field(description="文章ID")
    title: str = Field(description="文章标题")
    content: str = Field(default="", description="文章内容")
    author_id: int = Field(description="作者用户ID")
    status: str = Field(description="文章状态（published/draft）")

    @query(name='posts')
    async def get_all(cls, limit: int = 10, status: Optional[str] = None) -> List['PostEntity']:
        """获取所有文章（可按状态筛选）"""
        all_posts = list(posts_db.values())
        if status:
            return [p for p in all_posts if p.status == status][:limit]
        return all_posts[:limit]

    @query(name='post')
    async def get_by_id(cls, id: int) -> Optional['PostEntity']:
        """根据 ID 获取文章"""
        return posts_db.get(id)

    @mutation(name='createPost', description='创建新文章')
    async def create_post(cls, title: str, content: str, author_id: int, status: str = 'draft') -> 'PostEntity':
        """创建新文章并返回创建的文章对象"""
        global post_id_counter
        post_id_counter += 1
        new_post = PostEntity(
            id=post_id_counter,
            title=title,
            content=content,
            author_id=author_id,
            status=status
        )
        posts_db[post_id_counter] = new_post
        return new_post

    @mutation(name='updatePost')
    async def update_post(cls, id: int, title: Optional[str] = None, content: Optional[str] = None, status: Optional[str] = None) -> Optional['PostEntity']:
        """更新文章内容或状态"""
        if id in posts_db:
            post = posts_db[id]
            if title is not None:
                post.title = title
            if content is not None:
                post.content = content
            if status is not None:
                post.status = status
            return post
        return None

    @mutation(name='publishPost')
    async def publish_post(cls, id: int) -> Optional['PostEntity']:
        """发布文章（将状态改为 published）"""
        if id in posts_db:
            post = posts_db[id]
            post.status = 'published'
            return post
        return None

    @mutation(name='deletePost')
    async def delete_post(cls, id: int) -> bool:
        """删除文章，返回是否成功"""
        if id in posts_db:
            del posts_db[id]
            return True
        return False

    @mutation(name='createPostWithInput', description='使用 Input Type 创建新文章')
    async def create_post_with_input(cls, input: CreatePostInput) -> 'PostEntity':
        """使用 Input Type 创建新文章"""
        global post_id_counter
        post_id_counter += 1
        new_post = PostEntity(
            id=post_id_counter,
            title=input.title,
            content=input.content,
            author_id=input.author_id,
            status=input.status
        )
        posts_db[post_id_counter] = new_post
        return new_post

    @mutation(name='updatePostWithInput', description='使用 Input Type 更新文章')
    async def update_post_with_input(cls, id: int, input: UpdatePostInput) -> Optional['PostEntity']:
        """使用 Input Type 更新文章内容或状态"""
        if id in posts_db:
            post = posts_db[id]
            if input.title is not None:
                post.title = input.title
            if input.content is not None:
                post.content = input.content
            if input.status is not None:
                post.status = input.status
            return post
        return None


# Comment 实体
class CommentEntity(BaseModel, BaseEntity):
    """评论实体

    表示用户对文章的评论内容。
    """
    __relationships__ = [
        Relationship(field='author_id', target_kls=UserEntity, loader=user_loader, default_field_name='author'),
        Relationship(field='post_id', target_kls=PostEntity, loader=post_loader, default_field_name='post')
    ]
    id: int = Field(description="评论ID")
    text: str = Field(description="评论内容")
    author_id: int = Field(description="评论者用户ID")
    post_id: int = Field(description="被评论的文章ID")

    @query(name='comments')
    async def get_all(cls) -> List['CommentEntity']:
        """获取所有评论"""
        return list(comments_db.values())

    @mutation(name='createComment', description='创建新评论')
    async def create_comment(cls, text: str, author_id: int, post_id: int) -> 'CommentEntity':
        """创建新评论并返回创建的评论对象"""
        global comment_id_counter
        comment_id_counter += 1
        new_comment = CommentEntity(
            id=comment_id_counter,
            text=text,
            author_id=author_id,
            post_id=post_id
        )
        comments_db[comment_id_counter] = new_comment
        return new_comment

    @mutation(name='updateComment')
    async def update_comment(cls, id: int, text: Optional[str] = None) -> Optional['CommentEntity']:
        """更新评论内容"""
        if id in comments_db:
            comment = comments_db[id]
            if text is not None:
                comment.text = text
            return comment
        return None

    @mutation(name='deleteComment')
    async def delete_comment(cls, id: int) -> bool:
        """删除评论，返回是否成功"""
        if id in comments_db:
            del comments_db[id]
            return True
        return False


# 初始化模拟数据库
def init_db():
    """初始化模拟数据库"""
    global users_db, posts_db, comments_db

    users_db = {
        1: UserEntity(id=1, name="Alice", email="alice@example.com", role="admin"),
        2: UserEntity(id=2, name="Bob", email="bob@example.com", role="user"),
        3: UserEntity(id=3, name="Charlie", email="charlie@example.com", role="user"),
        4: UserEntity(id=4, name="Diana", email="diana@example.com", role="admin"),
    }

    posts_db = {
        1: PostEntity(id=1, title="First Post", content="Hello World!", author_id=1, status="published"),
        2: PostEntity(id=2, title="Second Post", content="GraphQL is awesome", author_id=2, status="published"),
        3: PostEntity(id=3, title="Third Post", content="Python tips", author_id=1, status="draft"),
        4: PostEntity(id=4, title="Fourth Post", content="FastAPI tutorial", author_id=3, status="published"),
    }

    comments_db = {
        1: CommentEntity(id=1, text="Great post!", author_id=2, post_id=1),
        2: CommentEntity(id=2, text="Thanks!", author_id=1, post_id=1),
        3: CommentEntity(id=3, text="Very helpful", author_id=3, post_id=2),
        4: CommentEntity(id=4, text="Nice tutorial", author_id=4, post_id=4),
    }


# 自动初始化
init_db()
