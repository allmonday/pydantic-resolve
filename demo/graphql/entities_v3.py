"""
V3 Entity Definitions - SQLAlchemy ORM + build_relationship

Uses SQLAlchemy ORM models with integration/sqlalchemy's build_relationship
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
from pydantic_resolve.integration.mapping import Mapping
from pydantic_resolve.integration.sqlalchemy import build_relationship


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

    posts: Mapped[List["PostOrm"]] = relationship(back_populates="author", order_by="PostOrm.id")
    comments: Mapped[List["CommentOrm"]] = relationship(back_populates="author", order_by="CommentOrm.id")


class PostOrm(Base):
    __tablename__ = "post"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(String, default="")
    author_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    status: Mapped[str] = mapped_column(String, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime)

    author: Mapped["UserOrm"] = relationship(back_populates="posts")
    comments: Mapped[List["CommentOrm"]] = relationship(back_populates="post", order_by="CommentOrm.id")


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


class UserEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="User ID")
    name: str = Field(description="User name")
    email: str = Field(description="Email address")
    role: str = Field(description="User role")
    created_at: datetime = Field(description="Created at")


class PostEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Post ID")
    title: str = Field(description="Post title")
    content: str = Field(default="", description="Post content")
    author_id: int = Field(description="Author user ID")
    status: str = Field(description="Post status")
    created_at: datetime = Field(description="Created at")


class CommentEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Comment ID")
    text: str = Field(description="Comment text")
    author_id: int = Field(description="Author user ID")
    post_id: int = Field(description="Post ID")
    created_at: datetime = Field(description="Created at")


# =====================================
# Query Functions
# =====================================


async def get_all_users(limit: int = 10, offset: int = 0) -> List[UserEntity]:
    """Get all users (paginated)."""
    async with async_session_factory() as session:
        stmt = select(UserOrm).offset(offset).limit(limit)
        result = await session.execute(stmt)
        rows = result.scalars().all()
    return [UserEntity.model_validate(r) for r in rows]


async def get_user_by_id(id: int) -> Optional[UserEntity]:
    """Get user by ID."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(UserOrm).where(UserOrm.id == id)
        )
        row = result.scalar_one_or_none()
    return UserEntity.model_validate(row) if row else None


async def get_all_posts(
    limit: int = 10, status: Optional[str] = None
) -> List[PostEntity]:
    """Get all posts (filterable by status)."""
    async with async_session_factory() as session:
        stmt = select(PostOrm)
        if status:
            stmt = stmt.where(PostOrm.status == status)
        stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        rows = result.scalars().all()
    return [PostEntity.model_validate(r) for r in rows]


async def get_post_by_id(id: int) -> Optional[PostEntity]:
    """Get post by ID."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(PostOrm).where(PostOrm.id == id)
        )
        row = result.scalar_one_or_none()
    return PostEntity.model_validate(row) if row else None


async def get_all_comments() -> List[CommentEntity]:
    """Get all comments."""
    async with async_session_factory() as session:
        result = await session.execute(select(CommentOrm))
        rows = result.scalars().all()
    return [CommentEntity.model_validate(r) for r in rows]


async def get_my_posts(limit: int = 10, _context: dict = None) -> List[PostEntity]:
    """Get posts by the current user (requires context)."""
    if _context is None:
        raise ValueError("Authentication required")
    user_id = _context.get('user_id')
    if user_id is None:
        raise ValueError("user_id is required in context")
    async with async_session_factory() as session:
        stmt = (
            select(PostOrm)
            .where(PostOrm.author_id == user_id)
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
    return [PostEntity.model_validate(r) for r in rows]


# =====================================
# Mutation Functions
# =====================================


async def create_user(
    name: str, email: str, role: str = "user"
) -> UserEntity:
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
        return UserEntity.model_validate(orm)


async def create_user_with_input(input: CreateUserInput) -> UserEntity:
    """Create user with input type."""
    return await create_user(name=input.name, email=input.email, role=input.role)


async def create_post(
    title: str,
    content: str,
    author_id: int,
    status: str = "draft",
) -> PostEntity:
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
        return PostEntity.model_validate(orm)


async def create_post_with_input(input: CreatePostInput) -> PostEntity:
    """Create post with input type."""
    return await create_post(
        title=input.title, content=input.content,
        author_id=input.author_id, status=input.status
    )


async def create_comment(
    text: str, author_id: int, post_id: int
) -> CommentEntity:
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
        return CommentEntity.model_validate(orm)


# =====================================
# ErDiagram Construction
# =====================================

# Step 1: Auto-generate relationship entities from ORM
relationship_entities = build_relationship(
    mappings=[
        Mapping(entity=UserEntity, orm=UserOrm),
        Mapping(entity=PostEntity, orm=PostOrm),
        Mapping(entity=CommentEntity, orm=CommentOrm),
    ],
    session_factory=session_factory,
)

# Step 2: Define query/mutation configs
qm_entities = [
    Entity(
        kls=UserEntity,
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
        kls=PostEntity,
        queries=[
            QueryConfig(
                method=get_all_posts, name="posts_v3",
                description="Get all posts (filterable by status)",
            ),
            QueryConfig(
                method=get_post_by_id, name="post_v3",
                description="Get post by ID",
            ),
            QueryConfig(
                method=get_my_posts, name="my_posts_v3",
                description="Get posts by the me (current use)",
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
        kls=CommentEntity,
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
            # --- Users (8) ---
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
                UserOrm(
                    id=5, name="Eve", email="eve@example.com",
                    role="user", created_at=datetime(2024, 2, 1, 9, 0, 0),
                ),
                UserOrm(
                    id=6, name="Frank", email="frank@example.com",
                    role="user", created_at=datetime(2024, 2, 5, 14, 0, 0),
                ),
                UserOrm(
                    id=7, name="Grace", email="grace@example.com",
                    role="user", created_at=datetime(2024, 2, 10, 16, 0, 0),
                ),
                UserOrm(
                    id=8, name="Henry", email="henry@example.com",
                    role="user", created_at=datetime(2024, 2, 15, 8, 30, 0),
                ),
            ])

            # --- Posts (15) ---
            session.add_all([
                PostOrm(
                    id=1, title="Getting Started with Python",
                    content="Python is a versatile programming language...",
                    author_id=1, status="published",
                    created_at=datetime(2024, 1, 10, 9, 0, 0),
                ),
                PostOrm(
                    id=2, title="GraphQL Best Practices",
                    content="Tips for designing efficient GraphQL schemas...",
                    author_id=1, status="published",
                    created_at=datetime(2024, 1, 15, 14, 0, 0),
                ),
                PostOrm(
                    id=3, title="Async Programming Guide",
                    content="Understanding async/await in Python...",
                    author_id=1, status="draft",
                    created_at=datetime(2024, 1, 20, 8, 0, 0),
                ),
                PostOrm(
                    id=4, title="Database Design Tips",
                    content="Normalization, indexing, and query optimization...",
                    author_id=1, status="published",
                    created_at=datetime(2024, 1, 25, 11, 0, 0),
                ),
                PostOrm(
                    id=5, title="FastAPI Deep Dive",
                    content="Exploring FastAPI's advanced features...",
                    author_id=2, status="published",
                    created_at=datetime(2024, 2, 3, 10, 30, 0),
                ),
                PostOrm(
                    id=6, title="Testing Strategies",
                    content="Unit tests, integration tests, and E2E testing...",
                    author_id=2, status="draft",
                    created_at=datetime(2024, 2, 8, 15, 0, 0),
                ),
                PostOrm(
                    id=7, title="Docker for Beginners",
                    content="Containerization basics and Docker Compose...",
                    author_id=3, status="published",
                    created_at=datetime(2024, 2, 12, 9, 0, 0),
                ),
                PostOrm(
                    id=8, title="Kubernetes in Production",
                    content="Lessons learned from running K8s at scale...",
                    author_id=3, status="published",
                    created_at=datetime(2024, 2, 18, 13, 0, 0),
                ),
                PostOrm(
                    id=9, title="Machine Learning Basics",
                    content="Introduction to supervised and unsupervised learning...",
                    author_id=3, status="archived",
                    created_at=datetime(2024, 2, 22, 16, 0, 0),
                ),
                PostOrm(
                    id=10, title="React Patterns",
                    content="Compound components, render props, and hooks...",
                    author_id=4, status="published",
                    created_at=datetime(2024, 3, 1, 10, 0, 0),
                ),
                PostOrm(
                    id=11, title="Vue.js vs React",
                    content="A practical comparison for new projects...",
                    author_id=4, status="published",
                    created_at=datetime(2024, 3, 5, 14, 0, 0),
                ),
                PostOrm(
                    id=12, title="CSS Architecture",
                    content="BEM, CSS Modules, and utility-first approaches...",
                    author_id=5, status="published",
                    created_at=datetime(2024, 3, 10, 9, 30, 0),
                ),
                PostOrm(
                    id=13, title="TypeScript Advanced Types",
                    content="Conditional types, mapped types, and template literals...",
                    author_id=5, status="published",
                    created_at=datetime(2024, 3, 15, 11, 0, 0),
                ),
                PostOrm(
                    id=14, title="Rust for Python Devs",
                    content="Memory ownership, borrowing, and lifetimes explained...",
                    author_id=6, status="draft",
                    created_at=datetime(2024, 3, 20, 8, 0, 0),
                ),
                PostOrm(
                    id=15, title="Go Concurrency Patterns",
                    content="Goroutines, channels, and select statements...",
                    author_id=7, status="published",
                    created_at=datetime(2024, 3, 25, 16, 0, 0),
                ),
            ])

            # --- Comments (32) ---
            session.add_all([
                # Post 1: 5 comments (hot post, good for pagination testing)
                CommentOrm(
                    id=1, text="Great introduction, very clear!", author_id=2, post_id=1,
                    created_at=datetime(2024, 1, 11, 10, 0, 0),
                ),
                CommentOrm(
                    id=2, text="Thanks for sharing!", author_id=1, post_id=1,
                    created_at=datetime(2024, 1, 11, 11, 0, 0),
                ),
                CommentOrm(
                    id=3, text="Could you cover type hints next?", author_id=3, post_id=1,
                    created_at=datetime(2024, 1, 12, 9, 0, 0),
                ),
                CommentOrm(
                    id=4, text="This helped me get started quickly.", author_id=5, post_id=1,
                    created_at=datetime(2024, 1, 13, 14, 0, 0),
                ),
                CommentOrm(
                    id=5, text="Bookmarked for reference!", author_id=4, post_id=1,
                    created_at=datetime(2024, 1, 14, 8, 0, 0),
                ),
                # Post 2: 3 comments
                CommentOrm(
                    id=6, text="Very helpful for schema design.", author_id=3, post_id=2,
                    created_at=datetime(2024, 1, 16, 10, 0, 0),
                ),
                CommentOrm(
                    id=7, text="The batching tips are golden.", author_id=4, post_id=2,
                    created_at=datetime(2024, 1, 17, 9, 0, 0),
                ),
                CommentOrm(
                    id=8, text="I used this in my project, works great.", author_id=6, post_id=2,
                    created_at=datetime(2024, 1, 18, 15, 0, 0),
                ),
                # Post 3: 1 comment (draft)
                CommentOrm(
                    id=9, text="Looking forward to the full version!", author_id=2, post_id=3,
                    created_at=datetime(2024, 1, 21, 10, 0, 0),
                ),
                # Post 4: 4 comments
                CommentOrm(
                    id=10, text="The indexing section was eye-opening.", author_id=5, post_id=4,
                    created_at=datetime(2024, 1, 26, 9, 0, 0),
                ),
                CommentOrm(
                    id=11, text="More on query optimization please!", author_id=2, post_id=4,
                    created_at=datetime(2024, 1, 27, 11, 0, 0),
                ),
                CommentOrm(
                    id=12, text="Applied this to my production DB.", author_id=7, post_id=4,
                    created_at=datetime(2024, 1, 28, 14, 0, 0),
                ),
                CommentOrm(
                    id=13, text="Great comparison of normalization levels.", author_id=3, post_id=4,
                    created_at=datetime(2024, 1, 29, 8, 0, 0),
                ),
                # Post 5: 3 comments
                CommentOrm(
                    id=14, text="FastAPI is amazing, thanks for the deep dive!", author_id=1, post_id=5,
                    created_at=datetime(2024, 2, 4, 10, 0, 0),
                ),
                CommentOrm(
                    id=15, text="The dependency injection section is excellent.", author_id=6, post_id=5,
                    created_at=datetime(2024, 2, 5, 9, 0, 0),
                ),
                CommentOrm(
                    id=16, text="Would love to see WebSocket examples.", author_id=3, post_id=5,
                    created_at=datetime(2024, 2, 6, 14, 0, 0),
                ),
                # Post 6: 1 comment (draft)
                CommentOrm(
                    id=17, text="When will this be published?", author_id=8, post_id=6,
                    created_at=datetime(2024, 2, 9, 10, 0, 0),
                ),
                # Post 7: 2 comments
                CommentOrm(
                    id=18, text="Docker Compose section saved me hours.", author_id=4, post_id=7,
                    created_at=datetime(2024, 2, 13, 10, 0, 0),
                ),
                CommentOrm(
                    id=19, text="Clear explanation of volumes vs bind mounts.", author_id=8, post_id=7,
                    created_at=datetime(2024, 2, 14, 11, 0, 0),
                ),
                # Post 8: 3 comments
                CommentOrm(
                    id=20, text="We use similar patterns at my company.", author_id=1, post_id=8,
                    created_at=datetime(2024, 2, 19, 10, 0, 0),
                ),
                CommentOrm(
                    id=21, text="Helm charts tips would be a great follow-up.", author_id=5, post_id=8,
                    created_at=datetime(2024, 2, 20, 9, 0, 0),
                ),
                CommentOrm(
                    id=22, text="The monitoring section is crucial.", author_id=7, post_id=8,
                    created_at=datetime(2024, 2, 21, 15, 0, 0),
                ),
                # Post 9: 1 comment (archived)
                CommentOrm(
                    id=23, text="Still relevant even though it's archived.", author_id=6, post_id=9,
                    created_at=datetime(2024, 2, 23, 10, 0, 0),
                ),
                # Post 10: 3 comments
                CommentOrm(
                    id=24, text="Compound components are so elegant!", author_id=2, post_id=10,
                    created_at=datetime(2024, 3, 2, 10, 0, 0),
                ),
                CommentOrm(
                    id=25, text="Custom hooks section is fantastic.", author_id=5, post_id=10,
                    created_at=datetime(2024, 3, 3, 14, 0, 0),
                ),
                CommentOrm(
                    id=26, text="I refactored my codebase after reading this.", author_id=8, post_id=10,
                    created_at=datetime(2024, 3, 4, 9, 0, 0),
                ),
                # Post 11: 2 comments
                CommentOrm(
                    id=27, text="Fair comparison, both have their strengths.", author_id=1, post_id=11,
                    created_at=datetime(2024, 3, 6, 10, 0, 0),
                ),
                CommentOrm(
                    id=28, text="I chose Vue for my last project.", author_id=7, post_id=11,
                    created_at=datetime(2024, 3, 7, 11, 0, 0),
                ),
                # Post 12: 2 comments
                CommentOrm(
                    id=29, text="Utility-first CSS changed my workflow.", author_id=2, post_id=12,
                    created_at=datetime(2024, 3, 11, 10, 0, 0),
                ),
                CommentOrm(
                    id=30, text="BEM still works well for large teams.", author_id=4, post_id=12,
                    created_at=datetime(2024, 3, 12, 9, 0, 0),
                ),
                # Post 13: 3 comments
                CommentOrm(
                    id=31, text="Mapped types blew my mind.", author_id=1, post_id=13,
                    created_at=datetime(2024, 3, 16, 10, 0, 0),
                ),
                CommentOrm(
                    id=32, text="Finally understand conditional types.", author_id=6, post_id=13,
                    created_at=datetime(2024, 3, 17, 14, 0, 0),
                ),
                CommentOrm(
                    id=33, text="Template literal types are underrated.", author_id=3, post_id=13,
                    created_at=datetime(2024, 3, 18, 9, 0, 0),
                ),
                # Post 14: 1 comment (draft)
                CommentOrm(
                    id=34, text="As a Python dev, this is very helpful!", author_id=8, post_id=14,
                    created_at=datetime(2024, 3, 21, 10, 0, 0),
                ),
                # Post 15: 2 comments
                CommentOrm(
                    id=35, text="Channels are powerful but tricky.", author_id=1, post_id=15,
                    created_at=datetime(2024, 3, 26, 10, 0, 0),
                ),
                CommentOrm(
                    id=36, text="Select statement examples are clear.", author_id=4, post_id=15,
                    created_at=datetime(2024, 3, 27, 11, 0, 0),
                ),
            ])
