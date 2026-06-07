"""Memory profiling: DFS vs BFS — focused on peak memory and call stack.

Uses tracemalloc for precise peak measurement.
The key insight is DFS uses recursion (_traverse calls _traverse) while
BFS uses a flat loop (_bfs_traverse iterates over levels).

Usage:
    uv run python benchmarks/bench_memory.py
"""

import asyncio
import tracemalloc
import sys

from pydantic import BaseModel
from pydantic_resolve import Loader, Resolver, build_list

# ──────────────────────────────────────────────────────────
# Data + Loaders + Views
# ──────────────────────────────────────────────────────────

def build_data(n_users, n_posts_per_user, n_comments_per_post):
    posts, comments = {}, {}
    for uid in range(1, n_users + 1):
        for j in range(n_posts_per_user):
            pid = uid * 100 + j
            posts[pid] = {"id": pid, "title": f"Post_{uid}_{j}", "author_id": uid}
    for pid in list(posts.keys()):
        for j in range(n_comments_per_post):
            cid = pid * 100 + j
            comments[cid] = {"id": cid, "content": f"Cmt_{pid}_{j}", "post_id": pid}
    return posts, comments


def make_loaders(posts_data, comments_data):
    async def posts_by_author_loader(author_ids: list[int]):
        result = [p for aid in author_ids for p in posts_data.values() if p["author_id"] == aid]
        return build_list(result, author_ids, lambda p: p["author_id"])

    async def comments_by_post_loader(post_ids: list[int]):
        result = [c for pid in post_ids for c in comments_data.values() if c["post_id"] == pid]
        return build_list(result, post_ids, lambda c: c["post_id"])

    return posts_by_author_loader, comments_by_post_loader


def make_views(posts_loader, comments_loader):
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


def fmt_kb(n: float) -> str:
    if abs(n) < 1024:
        return f"{n:.0f}B"
    return f"{n / 1024:.1f}KB"


def fmt_mb(n: float) -> str:
    return f"{n / 1024 / 1024:.2f}MB"


# ──────────────────────────────────────────────────────────
# Measurement
# ──────────────────────────────────────────────────────────

async def measure_peak(mode, n_users, posts_data, comments_data, n_iters=5):
    """Return (peak_bytes, per_iteration_peaks)."""
    loader_p, loader_c = make_loaders(posts_data, comments_data)
    UV = make_views(loader_p, loader_c)

    tracemalloc.start()
    peaks = []
    for _ in range(n_iters):
        users = [UV(id=i, name=f"User_{i}") for i in range(1, n_users + 1)]
        await Resolver(mode=mode).resolve(users)
        _, peak = tracemalloc.get_traced_memory()
        peaks.append(peak)
    tracemalloc.stop()
    return max(peaks), peaks


async def measure_call_depth(n_users, posts_data, comments_data):
    """Measure DFS max concurrent stack depth."""
    from pydantic_resolve import resolver as rmod

    _orig = rmod.Resolver._traverse
    depth = [0]
    max_depth = [0]

    async def _patched(self, node, parent):
        depth[0] += 1
        max_depth[0] = max(max_depth[0], depth[0])
        try:
            return await _orig(self, node, parent)
        finally:
            depth[0] -= 1

    rmod.Resolver._traverse = _patched
    loader_p, loader_c = make_loaders(posts_data, comments_data)
    UV = make_views(loader_p, loader_c)
    users = [UV(id=i, name=f"User_{i}") for i in range(1, n_users + 1)]
    await Resolver(mode="dfs").resolve(users)
    rmod.Resolver._traverse = _orig
    return max_depth[0]


# ──────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────

SCALES = [
    ("Small",   10, 3, 2),
    ("Medium",  50, 4, 3),
    ("Large",  200, 4, 3),
    ("XL",     500, 4, 3),
]

async def main():
    print("=" * 100)
    print("  Memory profiling: DFS vs BFS")
    print("  Tree: User → Post → Comment (3 levels)")
    print("=" * 100)

    # ── 1. Peak memory ──
    print(f"\n  {'Scale':<8s} {'Nodes':>14s} │ "
          f"{'DFS Peak':>10s} {'BFS Peak':>10s} {'Δ':>12s} {'Δ%':>7s}")
    print(f"  {'─' * 8} {'─' * 14}─┼─"
          f"{'─' * 10}─{'─' * 10}─{'─' * 12}─{'─' * 7}")

    for name, n_u, n_p, n_c in SCALES:
        label = f"{n_u}+{n_u*n_p}+{n_u*n_p*n_c}"
        pd, cd = build_data(n_u, n_p, n_c)
        dfs_peak, _ = await measure_peak("dfs", n_u, pd, cd)
        pd, cd = build_data(n_u, n_p, n_c)
        bfs_peak, _ = await measure_peak("bfs", n_u, pd, cd)
        delta = bfs_peak - dfs_peak
        pct = delta / dfs_peak * 100 if dfs_peak else 0

        print(f"  {name:<8s} {label:>14s} │ "
              f"{fmt_kb(dfs_peak):>10s} {fmt_kb(bfs_peak):>10s} "
              f"{'+' if delta >= 0 else ''}{fmt_kb(delta):>11s} {pct:>+6.1f}%")

    # ── 2. Memory growth per node ──
    print(f"\n  {'=' * 100}")
    print("  Peak memory per node (bytes)")
    print(f"  {'=' * 100}")

    for name, n_u, n_p, n_c in SCALES:
        total_nodes = n_u + n_u * n_p + n_u * n_p * n_c
        pd, cd = build_data(n_u, n_p, n_c)
        dfs_peak, _ = await measure_peak("dfs", n_u, pd, cd, n_iters=1)
        pd, cd = build_data(n_u, n_p, n_c)
        bfs_peak, _ = await measure_peak("bfs", n_u, pd, cd, n_iters=1)
        print(f"  {name:<8s}  DFS: {dfs_peak / total_nodes:.0f} B/node   "
              f"BFS: {bfs_peak / total_nodes:.0f} B/node   "
              f"Δ: {(dfs_peak - bfs_peak) / total_nodes:.0f} B/node saved by BFS")

    # ── 3. Call stack depth ──
    print(f"\n  {'=' * 100}")
    print("  Call stack depth (DFS _traverse recursion)")
    print(f"  {'=' * 100}")

    print(f"\n  Python recursion limit: {sys.getrecursionlimit()}")
    print(f"  {'Scale':<10s} {'Total Nodes':>12s} {'DFS Max Depth':>14s} {'BFS Depth':>10s}")
    print(f"  {'─' * 50}")

    for name, n_u, n_p, n_c in SCALES:
        pd, cd = build_data(n_u, n_p, n_c)
        dfs_d = await measure_call_depth(n_u, pd, cd)
        total = n_u + n_u * n_p + n_u * n_p * n_c
        print(f"  {name:<10s} {total:>12d} {dfs_d:>14d} {'1':>10s}")

    # ── 4. Where the memory goes ──
    print(f"\n  {'=' * 100}")
    print("  Memory composition analysis (Medium: 50 users)")
    print(f"  {'=' * 100}")

    # Single-iteration snapshots for composition analysis
    n_u, n_p, n_c = 50, 4, 3

    for mode in ["dfs", "bfs"]:
        pd, cd = build_data(n_u, n_p, n_c)
        loader_p, loader_c = make_loaders(pd, cd)
        UV = make_views(loader_p, loader_c)

        tracemalloc.start()
        snap_before = tracemalloc.take_snapshot()

        users = [UV(id=i, name=f"User_{i}") for i in range(1, n_u + 1)]
        await Resolver(mode=mode).resolve(users)

        _, peak = tracemalloc.get_traced_memory()
        snap_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        # Analyze by category
        diff = snap_after.compare_to(snap_before, "filename")
        categories = {
            "pydantic core": 0,
            "resolver.py": 0,
            "analysis.py": 0,
            "dataloader": 0,
            "asyncio": 0,
            "other": 0,
        }

        for stat in diff:
            fname = stat.traceback[0].filename
            if "pydantic/" in fname and "pydantic_resolve" not in fname:
                categories["pydantic core"] += stat.size
            elif "resolver.py" in fname:
                categories["resolver.py"] += stat.size
            elif "analysis.py" in fname:
                categories["analysis.py"] += stat.size
            elif "dataloader" in fname or "aiodataloader" in fname:
                categories["dataloader"] += stat.size
            elif "asyncio" in fname:
                categories["asyncio"] += stat.size
            else:
                categories["other"] += stat.size

        total_alloc = sum(categories.values())
        print(f"\n  {mode.upper()} — Peak: {fmt_kb(peak)}, Total alloc delta: {fmt_kb(total_alloc)}")
        print(f"  {'Category':<20s} {'Size':>10s} {'%':>6s}")
        print(f"  {'─' * 38}")
        for cat in sorted(categories, key=categories.get, reverse=True):
            sz = categories[cat]
            if sz > 0:
                print(f"  {cat:<20s} {fmt_kb(sz):>10s} {sz/total_alloc*100:>5.1f}%")

    # ── 5. Stack frame overhead estimation ──
    print(f"\n  {'=' * 100}")
    print("  Estimated stack frame overhead")
    print(f"  {'=' * 100}")

    # Each Python frame ~ 1-2KB (locals + code ref)
    # DFS has recursive frames, BFS doesn't
    for name, n_u, n_p, n_c in SCALES:
        pd, cd = build_data(n_u, n_p, n_c)
        dfs_d = await measure_call_depth(n_u, pd, cd)
        total = n_u + n_u * n_p + n_u * n_p * n_c
        # Each _traverse frame ~= ~1KB conservative estimate
        estimated_stack_kb = dfs_d * 1.0
        print(f"  {name:<8s}  DFS depth={dfs_d:<5d} → ~{estimated_stack_kb:.0f}KB stack   "
              f"BFS depth=1 → ~1KB stack")

    print("\n  Note: Stack memory is not counted by tracemalloc (heap profiler).")
    print("  The actual RSS difference includes both heap + stack.")


if __name__ == "__main__":
    asyncio.run(main())
