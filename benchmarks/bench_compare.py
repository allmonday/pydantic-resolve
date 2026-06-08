"""Generate benchmark report for pydantic-resolve Resolver.

Usage:
    uv run python benchmarks/bench_compare.py
    uv run python benchmarks/bench_compare.py --mysql
    uv run python benchmarks/bench_compare.py --mysql-latency
    uv run python benchmarks/bench_compare.py --ci --json benchmarks/results/benchmark_history.json
"""

import argparse
import asyncio
import datetime
import json
import os
import subprocess
import time
from statistics import quantiles
from typing import Optional

from sqlalchemy import ForeignKey, String, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from pydantic import BaseModel
from pydantic_resolve import Loader, Resolver, build_list, build_object

LATENCY = 0.002  # 2ms simulated round-trip per query
MAX_HISTORY = 30


def parse_args():
    p = argparse.ArgumentParser(description="pydantic-resolve benchmark runner")
    p.add_argument("--mysql", action="store_true")
    p.add_argument("--mysql-latency", action="store_true")
    p.add_argument("--ci", action="store_true", help="Reduced iterations for CI")
    p.add_argument("--json", type=str, default=None, metavar="PATH",
                    help="Append results to this JSON history file")
    return p.parse_args()

# ──────────────────────────────────────────────────────────
# ORM Models
# ──────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "bench_user"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    posts: Mapped[list["Post"]] = relationship(back_populates="author", lazy="noload", order_by="Post.id")
    comments: Mapped[list["Comment"]] = relationship(back_populates="author", lazy="noload", order_by="Comment.id")
    tasks: Mapped[list["Task"]] = relationship(back_populates="owner", lazy="noload", order_by="Task.id")

class Post(Base):
    __tablename__ = "bench_post"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    author_id: Mapped[int] = mapped_column(ForeignKey("bench_user.id"))
    author: Mapped[Optional["User"]] = relationship(back_populates="posts")
    comments: Mapped[list["Comment"]] = relationship(back_populates="post", lazy="noload", order_by="Comment.id")

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
    tasks: Mapped[list["Task"]] = relationship(back_populates="sprint", lazy="noload", order_by="Task.id")

class Task(Base):
    __tablename__ = "bench_task"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    sprint_id: Mapped[int] = mapped_column(ForeignKey("bench_sprint.id"))
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bench_user.id"), nullable=True)
    sprint: Mapped[Optional["Sprint"]] = relationship(back_populates="tasks")
    owner: Mapped[Optional["User"]] = relationship(back_populates="tasks")

# ──────────────────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────────────────

SQLITE_FILE_URL = "sqlite+aiosqlite:///bench_temp.db"
MYSQL_URL = "mysql+asyncmy://root:root@localhost:3306/pydantic_resolve_bench"

_engine = None
_session_factory = None

def _ensure_engine(use_mysql=False, use_mysql_latency=False):
    global _engine, _session_factory
    if _engine is None:
        if use_mysql or use_mysql_latency:
            url = MYSQL_URL
        else:
            url = SQLITE_FILE_URL
        _engine = create_async_engine(url, echo=False, pool_recycle=3600)
        _session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    return _engine, _session_factory

async def setup_db():
    engine, _ = _ensure_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

async def seed_data(n_users, n_sprints, n_tasks_per_sprint):
    _, sf = _ensure_engine()
    async with sf() as session:
        existing = (await session.execute(select(User))).scalar()
        if existing:
            return
        users = [User(name=f"User_{i}") for i in range(n_users)]
        for u in users:
            session.add(u)
        await session.commit()
        for u in users:
            await session.refresh(u)
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
        comments = []
        for i, p in enumerate(posts):
            n_c = 2 + (i % 2)
            for j in range(n_c):
                author = users[(i + j + 1) % n_users]
                c = Comment(content=f"Comment_{i}_{j}", post_id=p.id, author_id=author.id)
                session.add(c)
                comments.append(c)
        await session.commit()
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
                task = Task(title=f"Task_{task_id}", sprint_id=sprint.id, owner_id=owner.id)
                session.add(task)
                task_id += 1
        await session.commit()

# ──────────────────────────────────────────────────────────
# Loaders + Views
# ──────────────────────────────────────────────────────────

def _orm_to_dict(obj):
    return {c.key: getattr(obj, c.key) for c in obj.__table__.columns}

def _make_loaders(session_factory, use_mysql_latency=False):
    async def user_loader(user_ids):
        if use_mysql_latency:
            await asyncio.sleep(LATENCY)
        async with session_factory() as session:
            result = await session.execute(select(User).where(User.id.in_(user_ids)))
            users = [_orm_to_dict(u) for u in result.scalars().all()]
            return build_object(users, user_ids, lambda u: u["id"])

    async def posts_by_author_loader(author_ids):
        if use_mysql_latency:
            await asyncio.sleep(LATENCY)
        async with session_factory() as session:
            result = await session.execute(select(Post).where(Post.author_id.in_(author_ids)).order_by(Post.id))
            posts = [_orm_to_dict(p) for p in result.scalars().all()]
            return build_list(posts, author_ids, lambda p: p["author_id"])

    async def comments_by_post_loader(post_ids):
        if use_mysql_latency:
            await asyncio.sleep(LATENCY)
        async with session_factory() as session:
            result = await session.execute(select(Comment).where(Comment.post_id.in_(post_ids)).order_by(Comment.id))
            comments = [_orm_to_dict(c) for c in result.scalars().all()]
            return build_list(comments, post_ids, lambda c: c["post_id"])

    async def comments_by_author_loader(author_ids):
        if use_mysql_latency:
            await asyncio.sleep(LATENCY)
        async with session_factory() as session:
            result = await session.execute(select(Comment).where(Comment.author_id.in_(author_ids)).order_by(Comment.id))
            comments = [_orm_to_dict(c) for c in result.scalars().all()]
            return build_list(comments, author_ids, lambda c: c["author_id"])

    async def tasks_by_sprint_loader(sprint_ids):
        if use_mysql_latency:
            await asyncio.sleep(LATENCY)
        async with session_factory() as session:
            result = await session.execute(select(Task).where(Task.sprint_id.in_(sprint_ids)).order_by(Task.id))
            tasks = [_orm_to_dict(t) for t in result.scalars().all()]
            return build_list(tasks, sprint_ids, lambda t: t["sprint_id"])

    return {
        "user": user_loader,
        "posts_by_author": posts_by_author_loader,
        "comments_by_post": comments_by_post_loader,
        "comments_by_author": comments_by_author_loader,
        "tasks_by_sprint": tasks_by_sprint_loader,
    }

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

    class TaskToOwnerView(BaseModel):
        id: int
        title: str
        owner_id: int | None
        owner: UserView | None = None
        def resolve_owner(self, loader=Loader(user_loader)):
            return loader.load(self.owner_id)

    class SprintToTasksView(BaseModel):
        id: int
        name: str
        tasks: list[TaskToOwnerView] = []
        def resolve_tasks(self, loader=Loader(tasks_by_sprint)):
            return loader.load(self.id)

    class UserDeepView(BaseModel):
        id: int
        name: str
        posts: list[PostWithComments] = []
        def resolve_posts(self, loader=Loader(posts_by_author)):
            return loader.load(self.id)

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

async def bench_q1(sf, views):
    async with sf() as session:
        result = await session.execute(select(Task).order_by(Task.id))
        tasks = result.scalars().all()
    items = [views["TaskToOwner"](id=t.id, title=t.title, owner_id=t.owner_id) for t in tasks]
    return await Resolver().resolve(items)

async def bench_q2(sf, views):
    async with sf() as session:
        result = await session.execute(select(Sprint).order_by(Sprint.id))
        sprints = result.scalars().all()
    items = [views["SprintToTasks"](id=s.id, name=s.name) for s in sprints]
    return await Resolver().resolve(items)

async def bench_q3(sf, views):
    async with sf() as session:
        result = await session.execute(select(User).order_by(User.id))
        users = result.scalars().all()
    items = [views["UserDeep"](id=u.id, name=u.name) for u in users]
    return await Resolver().resolve(items)

async def bench_q4(sf, views):
    async with sf() as session:
        result = await session.execute(select(User).order_by(User.id))
        users = result.scalars().all()
    items = [views["UserWide"](id=u.id, name=u.name) for u in users]
    return await Resolver().resolve(items)

# ──────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────

N_WARMUP = 5
N_RUNS = 50
CI_WARMUP = 2
CI_RUNS = 20

async def run_bench(fn, n_runs):
    times = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        await fn()
        times.append(time.perf_counter() - t0)
    return times

def fmt_ms(seconds):
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.0f}us"
    return f"{seconds * 1000:.2f}ms"


def _get_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def _get_tag():
    try:
        tag = subprocess.check_output(
            ["git", "describe", "--tags", "--exact-match"], stderr=subprocess.DEVNULL
        ).decode().strip()
        return tag
    except Exception:
        return None


def _save_results(path, results):
    tag = _get_tag()
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "version": tag or _get_commit(),
        "results": results,
    }

    if os.path.exists(path):
        with open(path) as f:
            history = json.load(f)
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        history = {"version": 1, "entries": []}

    history["entries"].append(entry)
    history["entries"] = history["entries"][-MAX_HISTORY:]

    with open(path, "w") as f:
        json.dump(history, f, indent=2)

    print(f"  Results saved to {path} (entry {len(history['entries'])}/{MAX_HISTORY})")


async def main():
    global _engine, _session_factory

    args = parse_args()
    use_mysql = args.mysql or args.mysql_latency
    use_mysql_latency = args.mysql_latency
    n_warmup = CI_WARMUP if args.ci else N_WARMUP
    n_runs = CI_RUNS if args.ci else N_RUNS

    if use_mysql_latency:
        db_label = f"MySQL 8.0 (localhost, +{LATENCY*1000:.0f}ms simulated latency)"
    elif use_mysql:
        db_label = "MySQL 8.0 (localhost)"
    else:
        db_label = "SQLite (file: bench_temp.db)"

    print("=" * 100)
    print("  pydantic-resolve Benchmark")
    print(f"  Database: {db_label}")
    print("=" * 100)

    scenarios = [
        ("Q1", "Q1: 1-level (task→owner)", bench_q1),
        ("Q2", "Q2: 2-level (sprint→tasks→owner)", bench_q2),
        ("Q3", "Q3: 3-level linear (user→posts→comments)", bench_q3),
        ("Q4", "Q4: wide parallel (user→posts+comments)", bench_q4),
    ]

    scales = [
        ("Medium", 20, 10, 20),
        ("Large", 50, 20, 50),
        ("XLarge", 200, 50, 50),
    ]

    collected = {}

    for scale_name, n_users, n_sprints, n_tasks in scales:
        total_tasks = n_sprints * n_tasks
        print(f"\n  -- {scale_name} ({n_users} users, {n_sprints} sprints, {total_tasks} tasks) --")
        print()

        _engine = None
        _session_factory = None
        _, sf = _ensure_engine(use_mysql, use_mysql_latency)
        await setup_db()
        await seed_data(n_users, n_sprints, n_tasks)
        loaders = _make_loaders(sf, use_mysql_latency)
        views = _make_view_models(loaders)

        if scale_name == "Medium":
            print("  Verifying correctness...")
            try:
                await bench_q4(sf, views)
                print("  Correctness verification: PASSED\n")
            except Exception as e:
                print(f"  Correctness verification: FAILED ({e})\n")

        print(f"  {'Scenario':<45s} │ {'P50':>9s} {'P95':>9s} │ {'Total':>9s}")
        print(f"  {'─' * 45}─┼─{'─' * 9}─{'─' * 9}─┼─{'─' * 9}")

        for qkey, label, bench_fn in scenarios:
            async def run_fn(_fn=bench_fn, _sf=sf, _views=views):
                await _fn(_sf, _views)
            await run_bench(run_fn, n_warmup)
            times = await run_bench(run_fn, n_runs)

            p50 = quantiles(times, n=4)[0]
            p95 = quantiles(times, n=20)[18]
            total = sum(times)

            print(
                f"  {label:<45s} │ {fmt_ms(p50):>9s} {fmt_ms(p95):>9s} │ {fmt_ms(total):>9s}"
            )

            collected[f"{scale_name}_{qkey}"] = {
                "p50_ms": round(p50 * 1000, 3),
                "p95_ms": round(p95 * 1000, 3),
                "total_ms": round(total * 1000, 3),
                "n_runs": n_runs,
            }

    print()

    if args.json:
        _save_results(args.json, collected)


if __name__ == "__main__":
    asyncio.run(main())
