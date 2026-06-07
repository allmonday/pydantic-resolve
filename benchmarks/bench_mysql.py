"""pydantic-resolve Resolver performance benchmark.

Measures the time spent in Resolver().resolve() for various query patterns,
comparing DFS (current) vs BFS (future optimized) relationship resolution.

Scenarios:
  Q1: 1-level — tasks → owner (scalar)
  Q2: 2-level — sprints → tasks → owner
  Q3: 3-level linear — users → posts → comments
  Q4: wide parallel — users → posts + comments (parallel sibling fields)

Data scales: Small, Medium, Large

Usage:
    uv run python benchmarks/bench_mysql.py                  # SQLite in-memory
    uv run python benchmarks/bench_mysql.py --mysql          # MySQL (localhost:3306)
"""

import asyncio
import sys
import time
from statistics import mean, quantiles
from typing import Optional

USE_MYSQL = "--mysql" in sys.argv
USE_SQLITE_FILE = "--sqlite-file" in sys.argv
USE_BFS = "--bfs" in sys.argv

from sqlalchemy import ForeignKey, String, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel
from pydantic_resolve import Loader, Resolver, build_list, build_object


# ──────────────────────────────────────────────────────────
# ORM Models
# ──────────────────────────────────────────────────────────


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "bench_user"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))

    posts: Mapped[list["Post"]] = relationship(
        back_populates="author",
        lazy="noload",
        order_by="Post.id",
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="author",
        lazy="noload",
        order_by="Comment.id",
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="owner",
        lazy="noload",
        order_by="Task.id",
    )


class Post(Base):
    __tablename__ = "bench_post"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    author_id: Mapped[int] = mapped_column(ForeignKey("bench_user.id"))

    author: Mapped[Optional["User"]] = relationship(back_populates="posts")
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="post",
        lazy="noload",
        order_by="Comment.id",
    )


class Comment(Base):
    __tablename__ = "bench_comment"

    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str] = mapped_column(String(500))
    post_id: Mapped[int] = mapped_column(ForeignKey("bench_post.id"))
    author_id: Mapped[int] = mapped_column(ForeignKey("bench_user.id"))

    post: Mapped[Optional["Post"]] = relationship(back_populates="comments")
    author: Mapped[Optional["User"]] = relationship(back_populates="comments")


class Sprint(Base):
    __tablename__ = "bench_sprint"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="sprint",
        lazy="noload",
        order_by="Task.id",
    )


class Task(Base):
    __tablename__ = "bench_task"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    sprint_id: Mapped[int] = mapped_column(ForeignKey("bench_sprint.id"))
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bench_user.id"), nullable=True
    )

    sprint: Mapped[Optional["Sprint"]] = relationship(back_populates="tasks")
    owner: Mapped[Optional["User"]] = relationship(back_populates="tasks")


# ──────────────────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────────────────

_engine = None
_session_factory = None

SQLITE_URL = "sqlite+aiosqlite:///:memory:"
SQLITE_FILE_URL = "sqlite+aiosqlite:///bench_temp.db"
MYSQL_URL = "mysql+asyncmy://root:root@localhost:3306/pydantic_resolve_bench"


def _ensure_engine():
    global _engine, _session_factory
    if _engine is None:
        if USE_MYSQL:
            url = MYSQL_URL
        elif USE_SQLITE_FILE:
            url = SQLITE_FILE_URL
        else:
            url = SQLITE_URL
        _engine = create_async_engine(url, echo=False, pool_recycle=3600)
        _session_factory = async_sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False
        )
    return _engine, _session_factory


async def setup_db():
    engine, _ = _ensure_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def seed_data(n_users: int, n_sprints: int, n_tasks_per_sprint: int):
    _, sf = _ensure_engine()
    async with sf() as session:
        existing = (await session.execute(select(User))).scalar()
        if existing:
            return

        # Users
        users = [User(name=f"User_{i}") for i in range(n_users)]
        for u in users:
            session.add(u)
        await session.commit()
        for u in users:
            await session.refresh(u)

        # Posts: 3-5 per user
        posts = []
        for u in users:
            n_posts = 3 + (hash(u.name) % 3)
            for j in range(n_posts):
                p = Post(title=f"Post_{u.name}_{j}", author_id=u.id)
                session.add(p)
                posts.append(p)
        await session.commit()
        for p in posts:
            await session.refresh(p)

        # Comments: 2-3 per post, by other users
        comments = []
        for i, p in enumerate(posts):
            n_c = 2 + (i % 2)
            for j in range(n_c):
                author = users[(i + j + 1) % n_users]
                c = Comment(
                    content=f"Comment_{i}_{j}", post_id=p.id, author_id=author.id
                )
                session.add(c)
                comments.append(c)
        await session.commit()

        # Sprints & Tasks
        sprints = [Sprint(name=f"Sprint_{i}") for i in range(n_sprints)]
        for s in sprints:
            session.add(s)
        await session.commit()
        for s in sprints:
            await session.refresh(s)

        task_id = 0
        for sprint in sprints:
            for _j in range(n_tasks_per_sprint):
                owner = users[task_id % n_users]
                task = Task(
                    title=f"Task_{task_id}",
                    sprint_id=sprint.id,
                    owner_id=owner.id,
                )
                session.add(task)
                task_id += 1
        await session.commit()


# ──────────────────────────────────────────────────────────
# Loaders
# ──────────────────────────────────────────────────────────


def _orm_to_dict(obj):
    """Convert SQLAlchemy ORM object to dict for Pydantic validation."""
    return {c.key: getattr(obj, c.key) for c in obj.__table__.columns}


def _make_loaders(session_factory):
    """Create loader functions bound to the given session factory."""

    async def user_loader(user_ids: list[int]):
        async with session_factory() as session:
            result = await session.execute(
                select(User).where(User.id.in_(user_ids))
            )
            users = [_orm_to_dict(u) for u in result.scalars().all()]
            return build_object(users, user_ids, lambda u: u["id"])

    async def posts_by_author_loader(author_ids: list[int]):
        async with session_factory() as session:
            result = await session.execute(
                select(Post)
                .where(Post.author_id.in_(author_ids))
                .order_by(Post.id)
            )
            posts = [_orm_to_dict(p) for p in result.scalars().all()]
            return build_list(posts, author_ids, lambda p: p["author_id"])

    async def comments_by_post_loader(post_ids: list[int]):
        async with session_factory() as session:
            result = await session.execute(
                select(Comment)
                .where(Comment.post_id.in_(post_ids))
                .order_by(Comment.id)
            )
            comments = [_orm_to_dict(c) for c in result.scalars().all()]
            return build_list(comments, post_ids, lambda c: c["post_id"])

    async def comments_by_author_loader(author_ids: list[int]):
        async with session_factory() as session:
            result = await session.execute(
                select(Comment)
                .where(Comment.author_id.in_(author_ids))
                .order_by(Comment.id)
            )
            comments = [_orm_to_dict(c) for c in result.scalars().all()]
            return build_list(comments, author_ids, lambda c: c["author_id"])

    async def tasks_by_sprint_loader(sprint_ids: list[int]):
        async with session_factory() as session:
            result = await session.execute(
                select(Task)
                .where(Task.sprint_id.in_(sprint_ids))
                .order_by(Task.id)
            )
            tasks = [_orm_to_dict(t) for t in result.scalars().all()]
            return build_list(tasks, sprint_ids, lambda t: t["sprint_id"])

    return {
        "user": user_loader,
        "posts_by_author": posts_by_author_loader,
        "comments_by_post": comments_by_post_loader,
        "comments_by_author": comments_by_author_loader,
        "tasks_by_sprint": tasks_by_sprint_loader,
    }


# ──────────────────────────────────────────────────────────
# View Models
# ──────────────────────────────────────────────────────────


def _make_view_models(loaders):
    user_loader = loaders["user"]
    posts_by_author = loaders["posts_by_author"]
    comments_by_post = loaders["comments_by_post"]
    comments_by_author = loaders["comments_by_author"]
    tasks_by_sprint = loaders["tasks_by_sprint"]

    class UserView(BaseModel):
        id: int
        name: str

    class CommentView(BaseModel):
        id: int
        content: str

    class PostWithComments(BaseModel):
        id: int
        title: str
        comments: list[CommentView] = []

        def resolve_comments(self, loader=Loader(comments_by_post)):
            return loader.load(self.id)

    # Q1: 1-level (task → owner)
    class TaskToOwnerView(BaseModel):
        id: int
        title: str
        owner_id: int | None
        owner: UserView | None = None

        def resolve_owner(self, loader=Loader(user_loader)):
            return loader.load(self.owner_id)

    # Q2: 2-level (sprint → tasks → owner)
    class SprintToTasksView(BaseModel):
        id: int
        name: str
        tasks: list[TaskToOwnerView] = []

        def resolve_tasks(self, loader=Loader(tasks_by_sprint)):
            return loader.load(self.id)

    # Q3: 3-level linear (user → posts → comments)
    class UserDeepView(BaseModel):
        id: int
        name: str
        posts: list[PostWithComments] = []

        def resolve_posts(self, loader=Loader(posts_by_author)):
            return loader.load(self.id)

    # Q4: wide parallel (user → posts + comments)
    class UserWideView(BaseModel):
        id: int
        name: str
        posts: list[PostWithComments] = []
        comments: list[CommentView] = []

        def resolve_posts(self, loader=Loader(posts_by_author)):
            return loader.load(self.id)

        def resolve_comments(self, loader=Loader(comments_by_author)):
            return loader.load(self.id)

    return {
        "TaskToOwner": TaskToOwnerView,
        "SprintToTasks": SprintToTasksView,
        "UserDeep": UserDeepView,
        "UserWide": UserWideView,
    }


# ──────────────────────────────────────────────────────────
# Benchmark scenarios
# ──────────────────────────────────────────────────────────


async def bench_q1(session_factory, views, loaders):
    """Q1: 1-level — tasks → owner."""
    async with session_factory() as session:
        result = await session.execute(select(Task).order_by(Task.id))
        tasks = result.scalars().all()

    items = [views["TaskToOwner"](id=t.id, title=t.title, owner_id=t.owner_id) for t in tasks]
    return await Resolver(mode="bfs" if USE_BFS else "dfs").resolve(items)


async def bench_q2(session_factory, views, loaders):
    """Q2: 2-level — sprints → tasks → owner."""
    async with session_factory() as session:
        result = await session.execute(select(Sprint).order_by(Sprint.id))
        sprints = result.scalars().all()

    items = [views["SprintToTasks"](id=s.id, name=s.name) for s in sprints]
    return await Resolver(mode="bfs" if USE_BFS else "dfs").resolve(items)


async def bench_q3(session_factory, views, loaders):
    """Q3: 3-level linear — users → posts → comments."""
    async with session_factory() as session:
        result = await session.execute(select(User).order_by(User.id))
        users = result.scalars().all()

    items = [views["UserDeep"](id=u.id, name=u.name) for u in users]
    return await Resolver(mode="bfs" if USE_BFS else "dfs").resolve(items)


async def bench_q4(session_factory, views, loaders):
    """Q4: wide parallel — users → posts + comments."""
    async with session_factory() as session:
        result = await session.execute(select(User).order_by(User.id))
        users = result.scalars().all()

    items = [views["UserWide"](id=u.id, name=u.name) for u in users]
    return await Resolver(mode="bfs" if USE_BFS else "dfs").resolve(items)


# ──────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────

N_WARMUP = 5
N_RUNS = 50


async def run_bench(fn, n_runs: int) -> list[float]:
    times = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        await fn()
        times.append(time.perf_counter() - t0)
    return times


def fmt_ms(seconds: float) -> str:
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.0f}us"
    return f"{seconds * 1000:.2f}ms"


def print_result(label: str, times: list[float]):
    avg = mean(times)
    p50 = quantiles(times, n=4)[0]
    p95 = quantiles(times, n=20)[18]
    print(
        f"  {label:<55s} {fmt_ms(avg):>10s} {fmt_ms(p50):>10s} {fmt_ms(p95):>10s}"
    )


async def verify_correctness(session_factory, views, loaders):
    """Verify Q4 produces reasonable results."""
    result = await bench_q4(session_factory, views, loaders)
    assert isinstance(result, list)
    for u in result:
        assert hasattr(u, "posts"), f"User {u.id} missing posts"
        assert hasattr(u, "comments"), f"User {u.id} missing comments"
    print(f"  Correctness verification ({'BFS' if USE_BFS else 'DFS'}): PASSED\n")


async def main():
    if USE_MYSQL:
        db_label = "MySQL 8.0 (localhost)"
    elif USE_SQLITE_FILE:
        db_label = "SQLite (file: bench_temp.db)"
    else:
        db_label = "SQLite in-memory"
    mode_label = "BFS" if USE_BFS else "DFS"
    print("=" * 80)
    print(f"  pydantic-resolve Resolver Benchmark ({mode_label})")
    print(f"  Database: {db_label}")
    print("=" * 80)
    print()

    _, sf = _ensure_engine()

    scenarios = [
        ("Q1: 1-level (task→owner)", bench_q1),
        ("Q2: 2-level (sprint→tasks→owner)", bench_q2),
        ("Q3: 3-level linear (user→posts→comments)", bench_q3),
        ("Q4: wide parallel (user→posts+comments)", bench_q4),
    ]

    scales = [
        ("Small", 5, 3, 5),       # 15 tasks, ~20 posts, ~50 comments
        ("Medium", 20, 10, 20),   # 200 tasks, ~80 posts, ~200 comments
        ("Large", 50, 20, 50),    # 1000 tasks, ~200 posts, ~500 comments
    ]

    for scale_name, n_users, n_sprints, n_tasks in scales:
        total_tasks = n_sprints * n_tasks
        print(
            f"  -- {scale_name} ({n_users} users, {n_sprints} sprints, {total_tasks} tasks) --"
        )
        print()

        global _engine, _session_factory
        _engine = None
        _session_factory = None
        _, sf = _ensure_engine()

        await setup_db()
        await seed_data(n_users, n_sprints, n_tasks)

        loaders = _make_loaders(sf)
        views = _make_view_models(loaders)

        if scale_name == "Medium":
            print("  Verifying correctness...")
            await verify_correctness(sf, views, loaders)

        print(f"  {'Scenario':<55s} {'Avg':>10s} {'P50':>10s} {'P95':>10s}")
        print(f"  {'─' * 78}")

        for label, bench_fn in scenarios:

            async def run(_fn=bench_fn, _sf=sf, _views=views, _loaders=loaders):
                await _fn(_sf, _views, _loaders)

            await run_bench(run, N_WARMUP)
            times = await run_bench(run, N_RUNS)
            print_result(label, times)

        print()


if __name__ == "__main__":
    asyncio.run(main())
