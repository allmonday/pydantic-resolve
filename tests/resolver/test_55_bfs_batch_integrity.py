"""Verify BFS batch integrity — all same-level loads land in a single batch.

This test instruments the batch_load_fn call count and batch sizes
to prove that BFS guarantees optimal batching at each tree level.
"""

from typing import Optional

from pydantic import BaseModel
from pydantic_resolve import Loader, Resolver, build_list, build_object


# ──────────────────────────────────────────────────────────
# Instrumented loader factory
# ──────────────────────────────────────────────────────────

class BatchTracker:
    """Tracks how many times batch_load_fn is called and with what batch sizes."""

    def __init__(self):
        self.calls: list[int] = []  # list of batch sizes per call

    def reset(self):
        self.calls = []

    @property
    def total_calls(self) -> int:
        return len(self.calls)

    @property
    def total_keys(self) -> int:
        return sum(self.calls)

    @property
    def max_batch(self) -> int:
        return max(self.calls) if self.calls else 0


def make_tracked_loaders(tracker: BatchTracker):
    """Create loader functions that record batch sizes into tracker."""

    async def user_loader(user_ids: list[int]):
        tracker.calls.append(len(user_ids))
        users = [{"id": i, "name": f"User_{i}"} for i in user_ids]
        return build_object(users, user_ids, lambda u: u["id"])

    async def posts_by_author_loader(author_ids: list[int]):
        tracker.calls.append(len(author_ids))
        posts = []
        for aid in author_ids:
            for j in range(3):
                posts.append({"id": aid * 100 + j, "title": f"Post_{aid}_{j}", "author_id": aid})
        return build_list(posts, author_ids, lambda p: p["author_id"])

    async def comments_by_post_loader(post_ids: list[int]):
        tracker.calls.append(len(post_ids))
        comments = []
        for pid in post_ids:
            for j in range(2):
                comments.append({"id": pid * 100 + j, "content": f"Cmt_{pid}_{j}", "post_id": pid})
        return build_list(comments, post_ids, lambda c: c["post_id"])

    return user_loader, posts_by_author_loader, comments_by_post_loader


# ──────────────────────────────────────────────────────────
# View models
# ──────────────────────────────────────────────────────────

def make_views(user_loader, posts_loader, comments_loader):

    class CommentView(BaseModel):
        id: int
        content: str

    class PostView(BaseModel):
        id: int
        title: str
        comments: list[CommentView] = []

        def resolve_comments(self, loader=Loader(comments_loader)):
            return loader.load(self.id)

    class UserDeepView(BaseModel):
        id: int
        name: str
        posts: list[PostView] = []

        def resolve_posts(self, loader=Loader(posts_loader)):
            return loader.load(self.id)

    return UserDeepView


# ──────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────

async def _run(n_users: int, tracker: BatchTracker):
    user_loader, posts_loader, comments_loader = make_tracked_loaders(tracker)
    UserDeepView = make_views(user_loader, posts_loader, comments_loader)

    users = [UserDeepView(id=i, name=f"User_{i}") for i in range(1, n_users + 1)]
    tracker.reset()
    await Resolver().resolve(users)


async def test_bfs_2_level_batch_count():
    """With 10 users, BFS should produce exactly 2 batch calls (1 for posts, 1 for comments).

    The 2-level scenario (User→Post→Comment) has:
    - Level 1: 10 user loads → 1 batch of 10
    - Level 2: 30 post loads for comments → 1 batch of 30
    """
    tracker = BatchTracker()
    await _run(10, tracker)

    # Total keys: 10 posts + 30 comments = 40
    assert tracker.total_keys == 40

    # Exactly 2 batch calls (1 for posts, 1 for comments)
    assert tracker.total_calls == 2


async def test_bfs_single_level():
    """With only 1 level of resolve, should produce exactly 1 batch call."""
    tracker = BatchTracker()
    user_loader, _, _ = make_tracked_loaders(tracker)

    class TaskView(BaseModel):
        id: int
        owner_id: int
        owner: Optional[dict] = None

        def resolve_owner(self, loader=Loader(user_loader)):
            return loader.load(self.owner_id)

    tasks = [TaskView(id=i, owner_id=(i % 5) + 1) for i in range(20)]

    tracker.reset()
    await Resolver().resolve(tasks)

    assert tracker.total_calls == 1
    # DataLoader deduplicates: 20 tasks but only 5 unique owner_ids
    assert tracker.total_keys == 5


async def test_bfs_large_tree_batch_efficiency():
    """With 50 users, verify BFS consolidates batches efficiently."""
    tracker = BatchTracker()
    await _run(50, tracker)

    # DataLoader deduplicates keys:
    # Level 1: 50 unique user_ids → 50 keys for posts
    # Level 2: 150 unique post_ids → 150 keys for comments
    # Total: 50 + 150 = 200
    assert tracker.total_keys == 200

    # Exactly 2 batch calls
    assert tracker.total_calls == 2

    # Largest batch should be 150 (comments)
    assert tracker.max_batch == 150

    print(f"\n  BFS: {tracker.total_calls} batch calls, sizes={sorted(tracker.calls, reverse=True)}")
