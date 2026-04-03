"""
V3 Entity Definitions - SQLAlchemy ORM + build_relationship

Uses SQLAlchemy ORM models with contrib/sqlalchemy's build_relationship
to auto-generate relationship loaders from ORM declarations.

Differences from V2:
- SQLAlchemy ORM models instead of in-memory dicts
- build_relationship() auto-generates loaders from ORM relationships
- SQLite (aiosqlite) as database backend
- Queries/mutations use async SQLAlchemy sessions
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from pydantic_resolve import (
    Entity,
    ErDiagram,
    MutationConfig,
    QueryConfig,
    config_global_resolver,
)
from pydantic_resolve.contrib.mapping import Mapping
from pydantic_resolve.contrib.sqlalchemy import build_relationship


# =====================================
# Enum Types
# =====================================


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


class PostStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# =====================================
# Input Types for Mutations
# =====================================


class CreateUserInput(BaseModel):
    name: str = Field(description="User name")
    email: str = Field(description="Email address")
    role: UserRole = Field(default=UserRole.USER, description="User role")


class CreatePostInput(BaseModel):
    title: str = Field(description="Post title")
    content: str = Field(description="Post content")
    author_id: int = Field(description="Author ID")
    status: PostStatus = Field(default=PostStatus.DRAFT, description="Post status")


# =====================================
# Database Setup
# =====================================

engine = create_async_engine("sqlite+aiosqlite://", echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


def session_factory() -> AsyncSession:
    """Session factory used by build_relationship loaders."""
    return async_session_factory()


# =====================================
# SQLAlchemy ORM Models
# =====================================


class Base(DeclarativeBase):
    pass


class UserOrm(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime)

    posts: Mapped[List["PostOrm"]] = relationship(back_populates="author")
    comments: Mapped[List["CommentOrm"]] = relationship(back_populates="author")


class PostOrm(Base):
    __tablename__ = "post"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(String, default="")
    author_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    status: Mapped[str] = mapped_column(String, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime)

    author: Mapped["UserOrm"] = relationship(back_populates="posts")
    comments: Mapped[List["CommentOrm"]] = relationship(back_populates="post")


class CommentOrm(Base):
    __tablename__ = "comment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(String)
    author_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    post_id: Mapped[int] = mapped_column(ForeignKey("post.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime)

    author: Mapped["UserOrm"] = relationship(back_populates="comments")
    post: Mapped["PostOrm"] = relationship(back_populates="comments")


# =====================================
# Pydantic DTOs
# =====================================


class UserEntityV3(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="User ID")
    name: str = Field(description="User name")
    email: str = Field(description="Email address")
    role: str = Field(description="User role")
    created_at: datetime = Field(description="Created at")


class PostEntityV3(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Post ID")
    title: str = Field(description="Post title")
    content: str = Field(default="", description="Post content")
    author_id: int = Field(description="Author user ID")
    status: str = Field(description="Post status")
    created_at: datetime = Field(description="Created at")


class CommentEntityV3(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Comment ID")
    text: str = Field(description="Comment text")
    author_id: int = Field(description="Author user ID")
    post_id: int = Field(description="Post ID")
    created_at: datetime = Field(description="Created at")


# =====================================
# Query Functions
# =====================================


async def get_all_users(limit: int = 10, offset: int = 0) -> List[UserEntityV3]:
    """Get all users (paginated)."""
    async with async_session_factory() as session:
        stmt = select(UserOrm).offset(offset).limit(limit)
        result = await session.execute(stmt)
        rows = result.scalars().all()
    return [UserEntityV3.model_validate(r) for r in rows]


async def get_user_by_id(id: int) -> Optional[UserEntityV3]:
    """Get user by ID."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(UserOrm).where(UserOrm.id == id)
        )
        row = result.scalar_one_or_none()
    return UserEntityV3.model_validate(row) if row else None


async def get_all_posts(
    limit: int = 10, status: Optional[str] = None
) -> List[PostEntityV3]:
    """Get all posts (filterable by status)."""
    async with async_session_factory() as session:
        stmt = select(PostOrm)
        if status:
            stmt = stmt.where(PostOrm.status == status)
        stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        rows = result.scalars().all()
    return [PostEntityV3.model_validate(r) for r in rows]


async def get_post_by_id(id: int) -> Optional[PostEntityV3]:
    """Get post by ID."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(PostOrm).where(PostOrm.id == id)
        )
        row = result.scalar_one_or_none()
    return PostEntityV3.model_validate(row) if row else None


async def get_all_comments() -> List[CommentEntityV3]:
    """Get all comments."""
    async with async_session_factory() as session:
        result = await session.execute(select(CommentOrm))
        rows = result.scalars().all()
    return [CommentEntityV3.model_validate(r) for r in rows]


# =====================================
# Mutation Functions
# =====================================


async def create_user(
    name: str, email: str, role: str = "user"
) -> UserEntityV3:
    """Create a new user."""
    async with async_session_factory() as session:
        async with session.begin():
            orm = UserOrm(
                name=name, email=email, role=role,
                created_at=datetime.now()
            )
            session.add(orm)
            await session.flush()
            await session.refresh(orm)
        return UserEntityV3.model_validate(orm)


async def create_user_with_input(input: CreateUserInput) -> UserEntityV3:
    """Create user with input type."""
    return await create_user(name=input.name, email=input.email, role=input.role)


async def create_post(
    title: str,
    content: str,
    author_id: int,
    status: str = "draft",
) -> PostEntityV3:
    """Create a new post."""
    async with async_session_factory() as session:
        async with session.begin():
            orm = PostOrm(
                title=title, content=content, author_id=author_id,
                status=status, created_at=datetime.now()
            )
            session.add(orm)
            await session.flush()
            await session.refresh(orm)
        return PostEntityV3.model_validate(orm)


async def create_post_with_input(input: CreatePostInput) -> PostEntityV3:
    """Create post with input type."""
    return await create_post(
        title=input.title, content=input.content,
        author_id=input.author_id, status=input.status
    )


async def create_comment(
    text: str, author_id: int, post_id: int
) -> CommentEntityV3:
    """Create a new comment."""
    async with async_session_factory() as session:
        async with session.begin():
            orm = CommentOrm(
                text=text, author_id=author_id, post_id=post_id,
                created_at=datetime.now()
            )
            session.add(orm)
            await session.flush()
            await session.refresh(orm)
        return CommentEntityV3.model_validate(orm)


# =====================================
# ErDiagram Construction
# =====================================

# Step 1: Auto-generate relationship entities from ORM
relationship_entities = build_relationship(
    mappings=[
        Mapping(entity=UserEntityV3, orm=UserOrm),
        Mapping(entity=PostEntityV3, orm=PostOrm),
        Mapping(entity=CommentEntityV3, orm=CommentOrm),
    ],
    session_factory=session_factory,
)

# Step 2: Define query/mutation configs
qm_entities = [
    Entity(
        kls=UserEntityV3,
        queries=[
            QueryConfig(
                method=get_all_users, name="users_v3",
                description="Get all users (paginated)",
            ),
            QueryConfig(
                method=get_user_by_id, name="user_v3",
                description="Get user by ID",
            ),
        ],
        mutations=[
            MutationConfig(
                method=create_user, name="createUserV3",
                description="Create new user",
            ),
            MutationConfig(
                method=create_user_with_input, name="createUserWithInputV3",
                description="Create user with input type",
            ),
        ],
    ),
    Entity(
        kls=PostEntityV3,
        queries=[
            QueryConfig(
                method=get_all_posts, name="posts_v3",
                description="Get all posts (filterable by status)",
            ),
            QueryConfig(
                method=get_post_by_id, name="post_v3",
                description="Get post by ID",
            ),
        ],
        mutations=[
            MutationConfig(
                method=create_post, name="createPostV3",
                description="Create new post",
            ),
            MutationConfig(
                method=create_post_with_input, name="createPostWithInputV3",
                description="Create post with input type",
            ),
        ],
    ),
    Entity(
        kls=CommentEntityV3,
        queries=[
            QueryConfig(
                method=get_all_comments, name="comments_v3",
                description="Get all comments",
            ),
        ],
        mutations=[
            MutationConfig(
                method=create_comment, name="createCommentV3",
                description="Create new comment",
            ),
        ],
    ),
]

# Step 3: Merge - Q/M as base, add auto-generated relationships
diagram_v3 = ErDiagram(entities=qm_entities).add_relationship(relationship_entities)

# Step 4: Configure global resolver
config_global_resolver(diagram_v3)


# =====================================
# Database Initialization
# =====================================


async def init_db_v3() -> None:
    """Create tables and seed data. Must be called at app startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        async with session.begin():
            session.add_all([
                UserOrm(
                    id=1, name="Alice", email="alice@example.com",
                    role="admin", created_at=datetime(2024, 1, 1, 10, 0, 0),
                ),
                UserOrm(
                    id=2, name="Bob", email="bob@example.com",
                    role="user", created_at=datetime(2024, 1, 2, 11, 0, 0),
                ),
                UserOrm(
                    id=3, name="Charlie", email="charlie@example.com",
                    role="user", created_at=datetime(2024, 1, 3, 12, 0, 0),
                ),
                UserOrm(
                    id=4, name="Diana", email="diana@example.com",
                    role="admin", created_at=datetime(2024, 1, 4, 13, 0, 0),
                ),
            ])
            session.add_all([
                PostOrm(
                    id=1, title="First Post", content="Hello World!",
                    author_id=1, status="published",
                    created_at=datetime(2024, 1, 10, 9, 0, 0),
                ),
                PostOrm(
                    id=2, title="Second Post", content="GraphQL is awesome",
                    author_id=2, status="published",
                    created_at=datetime(2024, 1, 12, 14, 30, 0),
                ),
                PostOrm(
                    id=3, title="Third Post", content="Python tips",
                    author_id=1, status="draft",
                    created_at=datetime(2024, 1, 15, 8, 0, 0),
                ),
                PostOrm(
                    id=4, title="Fourth Post", content="FastAPI tutorial",
                    author_id=3, status="published",
                    created_at=datetime(2024, 1, 20, 16, 0, 0),
                ),
            ])
            session.add_all([
                CommentOrm(
                    id=1, text="Great post!", author_id=2, post_id=1,
                    created_at=datetime(2024, 1, 11, 10, 0, 0),
                ),
                CommentOrm(
                    id=2, text="Thanks!", author_id=1, post_id=1,
                    created_at=datetime(2024, 1, 11, 11, 0, 0),
                ),
                CommentOrm(
                    id=3, text="Very helpful", author_id=3, post_id=2,
                    created_at=datetime(2024, 1, 13, 15, 0, 0),
                ),
                CommentOrm(
                    id=4, text="Nice tutorial", author_id=4, post_id=4,
                    created_at=datetime(2024, 1, 21, 9, 0, 0),
                ),
            ])
