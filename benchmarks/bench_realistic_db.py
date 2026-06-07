"""BFS vs DFS improvement under simulated DB latency.

Injects artificial latency into loader functions to simulate
real network DB environments (0ms / 1ms / 5ms / 10ms / 50ms).

This answers: "does BFS improvement still matter when DB dominates?"

Usage:
    uv run python benchmarks/bench_realistic_db.py
"""

import asyncio
import time
from statistics import quantiles

from pydantic import BaseModel
from pydantic_resolve import Loader, Resolver, build_list

# ──────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────

N_USERS = 50
N_POSTS_PER_USER = 4
N_COMMENTS_PER_POST = 3
N_WARMUP = 5
N_RUNS = 30

# Simulated single-row DB latencies
LATENCIES_MS = [0, 0.5, 1, 2, 5, 10, 20, 50]

# ──────────────────────────────────────────────────────────
# In-memory data
# ──────────────────────────────────────────────────────────

USERS = {i: {"id": i, "name": f"User_{i}"} for i in range(1, N_USERS + 1)}
POSTS = {}
COMMENTS = {}

for _uid in range(1, N_USERS + 1):
    for _j in range(N_POSTS_PER_USER):
        _pid = _uid * 100 + _j
        POSTS[_pid] = {"id": _pid, "title": f"Post_{_uid}_{_j}", "author_id": _uid}

for _pid in list(POSTS.keys()):
    for _j in range(N_COMMENTS_PER_POST):
        _cid = _pid * 100 + _j
        COMMENTS[_cid] = {"id": _cid, "content": f"Cmt_{_pid}_{_j}", "post_id": _pid}


# ──────────────────────────────────────────────────────────
# Loaders with latency injection
# ──────────────────────────────────────────────────────────

def make_loaders(latency_s: float):
    """Create loaders with simulated DB latency (per batch call)."""

    async def posts_by_author_loader(author_ids: list[int]):
        if latency_s > 0:
            await asyncio.sleep(latency_s)
        result = []
        for aid in author_ids:
            for pid, p in POSTS.items():
                if p["author_id"] == aid:
                    result.append(p)
        return build_list(result, author_ids, lambda p: p["author_id"])

    async def comments_by_post_loader(post_ids: list[int]):
        if latency_s > 0:
            await asyncio.sleep(latency_s)
        result = []
        for pid in post_ids:
            for cid, c in COMMENTS.items():
                if c["post_id"] == pid:
                    result.append(c)
        return build_list(result, post_ids, lambda c: c["post_id"])

    return posts_by_author_loader, comments_by_post_loader


# ──────────────────────────────────────────────────────────
# View models (factory)
# ──────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────
# Benchmark
# ──────────────────────────────────────────────────────────

async def run_once(mode: str, latency_s: float):
    posts_loader, comments_loader = make_loaders(latency_s)
    UserDeepView = make_views(posts_loader, comments_loader)
    users = [UserDeepView(id=i, name=f"User_{i}") for i in range(1, N_USERS + 1)]
    t0 = time.perf_counter()
    await Resolver(mode=mode).resolve(users)
    return time.perf_counter() - t0


async def bench_mode(mode: str, latency_s: float, n_runs: int) -> list[float]:
    # warmup
    for _ in range(N_WARMUP):
        await run_once(mode, latency_s)
    # measure
    times = []
    for _ in range(n_runs):
        t = await run_once(mode, latency_s)
        times.append(t)
    return times


def fmt_ms(seconds: float) -> str:
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.0f}us"
    return f"{seconds * 1000:.2f}ms"


async def main():
    print("=" * 95)
    print("  BFS vs DFS under simulated DB latency")
    print(f"  Tree: {N_USERS} users → {N_USERS * N_POSTS_PER_USER} posts → "
          f"{N_USERS * N_POSTS_PER_USER * N_COMMENTS_PER_POST} comments  "
          f"({N_RUNS} runs per mode)")
    print("  DataLoader batches: 2 (posts + comments), same for both modes")
    print("=" * 95)

    header = (
        f"  {'Latency/batch':>14s} │"
        f"  {'DFS P50':>10s} {'DFS P95':>10s} │"
        f"  {'BFS P50':>10s} {'BFS P95':>10s} │"
        f"  {'Δ P50':>10s} {'Δ%':>7s}"
    )
    print(header)
    print(f"  {'─' * 14}─┼─{'─' * 10}─{'─' * 10}─┼─{'─' * 10}─{'─' * 10}─┼─{'─' * 10}─{'─' * 7}")

    results = []

    for latency_ms in LATENCIES_MS:
        latency_s = latency_ms / 1000.0

        dfs_times = await bench_mode("dfs", latency_s, N_RUNS)
        bfs_times = await bench_mode("bfs", latency_s, N_RUNS)

        dfs_p50 = quantiles(dfs_times, n=4)[0]
        dfs_p95 = quantiles(dfs_times, n=20)[18]
        bfs_p50 = quantiles(bfs_times, n=4)[0]
        bfs_p95 = quantiles(bfs_times, n=20)[18]

        delta = bfs_p50 - dfs_p50
        pct = (delta / dfs_p50) * 100 if dfs_p50 > 0 else 0

        latency_label = f"{latency_ms}ms" if latency_ms >= 1 else f"{latency_ms * 1000:.0f}us" if latency_ms > 0 else "0 (memory)"

        print(
            f"  {latency_label:>14s} │"
            f"  {fmt_ms(dfs_p50):>10s} {fmt_ms(dfs_p95):>10s} │"
            f"  {fmt_ms(bfs_p50):>10s} {fmt_ms(bfs_p95):>10s} │"
            f"  {fmt_ms(abs(delta)):>10s} {pct:>6.1f}%"
        )

        results.append({
            "latency_ms": latency_ms,
            "dfs_p50": dfs_p50,
            "bfs_p50": bfs_p50,
            "delta_pct": pct,
        })

    # Summary
    print(f"\n  {'=' * 93}")
    print("  Summary: BFS improvement vs DFS by DB latency tier")
    print(f"  {'=' * 93}")
    print()
    print(f"  {'Scenario':<35s} {'Latency/batch':>14s} {'BFS Δ%':>8s} {'Verdict':>20s}")
    print(f"  {'─' * 80}")

    verdicts = [
        (0, "Pure computation", "In-memory, no DB"),
        (0.5, "Fast local SQLite", "Local SSD cache"),
        (1, "Local SQLite file", "Same-machine DB"),
        (2, "Same-rack DB", "Low-latency network"),
        (5, "Same-DC DB", "Typical cloud DB"),
        (10, "Cross-AZ DB", "Cloud multi-AZ"),
        (20, "Cross-region (close)", "Regional replica"),
        (50, "Cross-region (far)", "Cross-region replica"),
    ]

    for latency_ms, env, desc in verdicts:
        r = next(r for r in results if r["latency_ms"] == latency_ms)
        pct = r["delta_pct"]
        if abs(pct) > 20:
            tag = "Significant"
        elif abs(pct) > 10:
            tag = "Noticeable"
        elif abs(pct) > 5:
            tag = "Marginal"
        else:
            tag = "Negligible"
        print(f"  {env:<35s} {latency_ms:>10.1f}ms   {pct:>+7.1f}%  {tag:>20s}")

    # Breakdown: compute time vs DB time
    print(f"\n  {'=' * 93}")
    print("  Time budget breakdown (P50, per resolve call)")
    print(f"  {'=' * 93}")

    r0 = results[0]  # 0ms latency
    python_overhead_dfs = r0["dfs_p50"]
    python_overhead_bfs = r0["bfs_p50"]
    python_savings = python_overhead_dfs - python_overhead_bfs

    print("\n  Python overhead (0ms latency):")
    print(f"    DFS: {fmt_ms(python_overhead_dfs)}")
    print(f"    BFS: {fmt_ms(python_overhead_bfs)}")
    print(f"    Savings: {fmt_ms(python_savings)} ({python_savings/python_overhead_dfs*100:.1f}%)")

    print("\n  With 2 batched queries per request:")
    for latency_ms in [1, 5, 10]:
        db_time = 2 * latency_ms / 1000.0  # 2 batches
        total_dfs = python_overhead_dfs + db_time
        total_bfs = python_overhead_bfs + db_time
        pct_improvement = (total_dfs - total_bfs) / total_dfs * 100
        print(f"    @ {latency_ms}ms/batch: DFS={fmt_ms(total_dfs)}, BFS={fmt_ms(total_bfs)}, "
              f"improvement={pct_improvement:.1f}%")

    for latency_ms in [10, 20, 50]:
        db_time = 2 * latency_ms / 1000.0
        total_dfs = python_overhead_dfs + db_time
        total_bfs = python_overhead_bfs + db_time
        pct_improvement = (total_dfs - total_bfs) / total_dfs * 100
        print(f"    @ {latency_ms}ms/batch: DFS={fmt_ms(total_dfs)}, BFS={fmt_ms(total_bfs)}, "
              f"improvement={pct_improvement:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
