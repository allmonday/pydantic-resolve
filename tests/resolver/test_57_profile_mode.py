"""Verify debug/profile mode collects timing data during BFS traversal.

When Resolver(debug=True) is used, self.performance should contain
non-empty timing records keyed by ancestor class path.
"""

from pydantic import BaseModel
from pydantic_resolve import Loader, Resolver, build_list, build_object

import pytest


# ──────────────────────────────────────────────────────────
# Test helpers
# ──────────────────────────────────────────────────────────

async def _user_loader(user_ids: list[int]):
    users = [{"id": i, "name": f"User_{i}"} for i in user_ids]
    return build_object(users, user_ids, lambda u: u["id"])


async def _posts_by_user_loader(user_ids: list[int]):
    posts = []
    for uid in user_ids:
        for j in range(2):
            posts.append({"id": uid * 100 + j, "title": f"Post_{uid}_{j}", "author_id": uid})
    return build_list(posts, user_ids, lambda p: p["author_id"])


# ──────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_profile_single_level():
    """Single-level resolve should produce timing data with root class name as key."""

    class TaskView(BaseModel):
        id: int
        owner_id: int
        owner: dict | None = None

        def resolve_owner(self, loader=Loader(_user_loader)):
            return loader.load(self.owner_id)

    tasks = [TaskView(id=i, owner_id=(i % 3) + 1) for i in range(5)]
    resolver = Resolver(debug=True)
    await resolver.resolve(tasks)

    # Should have timing data
    assert len(resolver.performance.full_path_timer) > 0

    # Key should be just the class name (no parent)
    keys = list(resolver.performance.full_path_timer.keys())
    assert "TaskView" in keys
    assert resolver.performance.full_path_timer["TaskView"].records
    assert resolver.performance.full_path_timer["TaskView"].average >= 0


@pytest.mark.asyncio
async def test_profile_multi_level():
    """Multi-level resolve should produce keys with ancestor paths."""

    class PostView(BaseModel):
        id: int
        title: str

    class UserView(BaseModel):
        id: int
        name: str
        posts: list[PostView] = []

        def resolve_posts(self, loader=Loader(_posts_by_user_loader)):
            return loader.load(self.id)

    users = [UserView(id=i, name=f"User_{i}") for i in range(1, 4)]
    resolver = Resolver(debug=True)
    await resolver.resolve(users)

    keys = list(resolver.performance.full_path_timer.keys())

    # Root level: "UserView" (resolve + post phases)
    assert "UserView" in keys

    # Child level: "UserView.PostView"
    assert "UserView.PostView" in keys

    # Both should have records
    assert resolver.performance.full_path_timer["UserView"].records
    assert resolver.performance.full_path_timer["UserView.PostView"].records


@pytest.mark.asyncio
async def test_profile_with_post_methods():
    """Post methods should contribute to timing data."""

    class ItemView(BaseModel):
        value: int
        doubled: int = 0

        def post_doubled(self):
            return self.value * 2

    items = [ItemView(value=i) for i in range(3)]
    resolver = Resolver(debug=True)
    result = await resolver.resolve(items)

    # Verify correctness
    assert [r.doubled for r in result] == [0, 2, 4]

    # Should have timing data (post phase timed)
    assert "ItemView" in resolver.performance.full_path_timer
    timer = resolver.performance.full_path_timer["ItemView"]
    assert len(timer.records) > 0


@pytest.mark.asyncio
async def test_profile_disabled_by_default():
    """Without debug=True, no timing data should be collected."""

    class SimpleView(BaseModel):
        id: int

    resolver = Resolver()
    await resolver.resolve([SimpleView(id=1)])

    assert len(resolver.performance.full_path_timer) == 0


@pytest.mark.asyncio
async def test_profile_list_root():
    """Resolving a list of root objects should produce per-instance timer records."""

    class RootView(BaseModel):
        id: int

    roots = [RootView(id=i) for i in range(5)]
    resolver = Resolver(debug=True)
    await resolver.resolve(roots)

    assert "RootView" in resolver.performance.full_path_timer
    # Each root instance contributes one record in Phase B-2
    # (Phase A has no resolve methods, so no timing there;
    #  Phase B-2 processes every node even if it has no post methods)
    timer = resolver.performance.full_path_timer["RootView"]
    assert len(timer.records) >= 1
