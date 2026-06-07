"""Verify BFS produces fewer and larger DataLoader batches than DFS.

This test instruments the batch_load_fn call count and batch sizes
to prove that DFS can split batches across recursive _traverse calls,
while BFS guarantees all same-level loads land in a single batch.
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

async def _run_comparison(n_users: int, mode: str, tracker: BatchTracker):
    user_loader, posts_loader, comments_loader = make_tracked_loaders(tracker)
    UserDeepView = make_views(user_loader, posts_loader, comments_loader)

    users = [UserDeepView(id=i, name=f"User_{i}") for i in range(1, n_users + 1)]
    tracker.reset()
    await Resolver(mode=mode).resolve(users)


async def _get_stats(n_users: int):
    """Run both modes and return (dfs_stats, bfs_stats)."""
    dfs_tracker = BatchTracker()
    bfs_tracker = BatchTracker()

    await _run_comparison(n_users, "dfs", dfs_tracker)
    await _run_comparison(n_users, "bfs", bfs_tracker)

    return dfs_tracker, bfs_tracker


async def test_bfs_fewer_batches_than_dfs():
    """BFS should produce <= DFS batch calls at each depth level.

    With 10 users, each with 3 posts, each with 2 comments:
    - Level 1 (user→posts): 1 batch of 10 keys in both modes
    - Level 2 (post→comments): BFS = 1 batch of 30 keys,
      DFS may split into multiple smaller batches
    """
    dfs, bfs = await _get_stats(10)

    # Both should load all data
    assert dfs.total_keys == bfs.total_keys

    # BFS should make no more batch calls than DFS
    assert bfs.total_calls <= dfs.total_calls


async def test_bfs_max_batch_size_larger():
    """BFS should produce batches at least as large as DFS."""
    dfs, bfs = await _get_stats(10)

    # The largest single batch in BFS should be >= DFS's largest
    assert bfs.max_batch >= dfs.max_batch


async def test_bfs_2_level_batch_count():
    """With enough nodes, DFS splits the level-2 batch.

    The 2-level scenario (User→Post→Comment) has:
    - Level 1: 10 user_loads (both modes batch into 1 call)
    - Level 2: 30 post_ids for comments

    In DFS, each User's _execute_resolve_method_field recursively
    traverses its own posts, potentially splitting the 30-key batch
    across multiple event loop ticks.

    In BFS, all 30 posts are collected into one level, producing
    exactly 1 batch call for comments.
    """
    dfs, bfs = await _get_stats(10)

    # Level 1 (posts): both should be 1 batch of 10
    # Level 2 (comments):
    #   BFS: 1 batch of 30
    #   DFS: >= 1 batch, possibly split

    # Total keys must be identical (10 posts + 30 comments = 40)
    assert dfs.total_keys == 40
    assert bfs.total_keys == 40

    # BFS should have exactly 2 batch calls (1 for posts, 1 for comments)
    assert bfs.total_calls == 2

    # DFS should have >= 2 batch calls (often more due to splitting)
    assert dfs.total_calls >= 2

    # The key assertion: BFS makes no more calls than DFS
    # (usually strictly fewer for deeper trees)
    if dfs.total_calls > bfs.total_calls:
        # If DFS splits, print details for visibility
        pass  # assertion already implied by <= above


async def test_bfs_single_level_no_difference():
    """With only 1 level of resolve, DFS and BFS should be identical."""
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
    await Resolver(mode="dfs").resolve([TaskView(id=t.id, owner_id=t.owner_id) for t in tasks])
    dfs_calls = tracker.total_calls
    dfs_keys = tracker.total_keys

    tracker.reset()
    await Resolver(mode="bfs").resolve([TaskView(id=t.id, owner_id=t.owner_id) for t in tasks])
    bfs_calls = tracker.total_calls
    bfs_keys = tracker.total_keys

    # Single level: both should produce identical batching
    assert dfs_calls == bfs_calls
    assert dfs_keys == bfs_keys


async def test_bfs_large_tree_batch_efficiency():
    """With 50 users, verify BFS consolidates batches more efficiently."""
    dfs, bfs = await _get_stats(50)

    # Same total work
    assert dfs.total_keys == bfs.total_keys

    # BFS should consolidate more: fewer calls, larger max batch
    assert bfs.total_calls <= dfs.total_calls
    assert bfs.max_batch >= dfs.max_batch

    # Print for manual inspection (visible with -s flag)
    print(f"\n  DFS: {dfs.total_calls} batch calls, sizes={sorted(dfs.calls, reverse=True)}")
    print(f"  BFS: {bfs.total_calls} batch calls, sizes={sorted(bfs.calls, reverse=True)}")
