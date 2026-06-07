"""cProfile comparison: DFS vs BFS execution mode.

Runs the same 3-level resolve tree (User→Post→Comment) under cProfile
for both modes, then prints a side-by-side diff of the top functions
by cumulative time.

Usage:
    uv run python benchmarks/profile_dfs_vs_bfs.py
"""

import asyncio
import cProfile
import pstats
import io
from pydantic import BaseModel
from pydantic_resolve import Loader, Resolver, build_list


# ──────────────────────────────────────────────────────────
# In-memory data
# ──────────────────────────────────────────────────────────

N_USERS = 50
N_POSTS_PER_USER = 4
N_COMMENTS_PER_POST = 3

# Pre-build data
USERS = {i: {"id": i, "name": f"User_{i}"} for i in range(1, N_USERS + 1)}
POSTS = {}
COMMENTS = {}

for uid in range(1, N_USERS + 1):
    for j in range(N_POSTS_PER_USER):
        pid = uid * 100 + j
        POSTS[pid] = {"id": pid, "title": f"Post_{uid}_{j}", "author_id": uid}

for pid in list(POSTS.keys()):
    for j in range(N_COMMENTS_PER_POST):
        cid = pid * 100 + j
        COMMENTS[cid] = {"id": cid, "content": f"Cmt_{pid}_{j}", "post_id": pid}


# ──────────────────────────────────────────────────────────
# Loaders
# ──────────────────────────────────────────────────────────

async def posts_by_author_loader(author_ids: list[int]):
    result = []
    for aid in author_ids:
        for pid, p in POSTS.items():
            if p["author_id"] == aid:
                result.append(p)
    return build_list(result, author_ids, lambda p: p["author_id"])


async def comments_by_post_loader(post_ids: list[int]):
    result = []
    for pid in post_ids:
        for cid, c in COMMENTS.items():
            if c["post_id"] == pid:
                result.append(c)
    return build_list(result, post_ids, lambda c: c["post_id"])


# ──────────────────────────────────────────────────────────
# View models
# ──────────────────────────────────────────────────────────

class CommentView(BaseModel):
    id: int
    content: str


class PostView(BaseModel):
    id: int
    title: str
    comments: list[CommentView] = []

    def resolve_comments(self, loader=Loader(comments_by_post_loader)):
        return loader.load(self.id)


class UserDeepView(BaseModel):
    id: int
    name: str
    posts: list[PostView] = []

    def resolve_posts(self, loader=Loader(posts_by_author_loader)):
        return loader.load(self.id)


# ──────────────────────────────────────────────────────────
# Profiling helpers
# ──────────────────────────────────────────────────────────

def build_users():
    return [UserDeepView(id=i, name=f"User_{i}") for i in range(1, N_USERS + 1)]


async def run_resolve(mode: str, n_iterations: int = 20):
    """Run resolver n times to get stable profiling data."""
    for _ in range(n_iterations):
        users = build_users()
        await Resolver(mode=mode).resolve(users)


def profile_mode(mode: str, n_iterations: int = 20) -> pstats.Stats:
    """Profile a single mode and return Stats object."""
    pr = cProfile.Profile()
    pr.enable()
    asyncio.run(run_resolve(mode, n_iterations))
    pr.disable()
    return pstats.Stats(pr)


def filter_stats(stats: pstats.Stats, prefix: str = "pydantic_resolve") -> dict:
    """Extract pydantic_resolve function stats into a dict keyed by function name."""
    result = {}
    stats.sort_stats("cumulative")

    # Use internal stats dict
    for (filename, line, func_name), (cc, nc, tt, ct, callers) in stats.stats.items():
        if prefix in filename or "resolver.py" in filename or "analysis.py" in filename or "conversion.py" in filename:
            short_name = f"{func_name} (L{line})"
            result[short_name] = {
                "calls": nc,
                "cumtime": ct,
                "tottime": tt,
            }
    return result


def print_comparison(dfs_stats: dict, bfs_stats: dict):
    """Print a comparison table."""
    all_keys = sorted(
        set(dfs_stats.keys()) | set(bfs_stats.keys()),
        key=lambda k: dfs_stats.get(k, bfs_stats.get(k, {})).get("cumtime", 0),
        reverse=True,
    )

    print(f"\n{'Function':<55s} {'DFS calls':>10s} {'BFS calls':>10s} {'DFS cum':>10s} {'BFS cum':>10s} {'Δ calls':>10s} {'Δ cum':>10s}")
    print("─" * 115)

    for key in all_keys:
        d = dfs_stats.get(key, {"calls": 0, "cumtime": 0, "tottime": 0})
        b = bfs_stats.get(key, {"calls": 0, "cumtime": 0, "tottime": 0})

        d_calls, b_calls = d["calls"], b["calls"]
        d_cum, b_cum = d["cumtime"], b["cumtime"]
        delta_calls = b_calls - d_calls
        delta_cum = b_cum - d_cum

        if d_cum > 0.001 or b_cum > 0.001:  # skip trivial entries
            print(
                f"{key:<55s} {d_calls:>10d} {b_calls:>10d} "
                f"{d_cum:>10.3f} {b_cum:>10.3f} "
                f"{delta_calls:>+10d} {delta_cum:>+10.3f}"
            )


def print_top_stats(stats: pstats.Stats, label: str, n: int = 30):
    """Print top-N functions by cumulative time."""
    print(f"\n{'=' * 80}")
    print(f"  {label} — Top {n} by cumulative time")
    print(f"{'=' * 80}")

    stream = io.StringIO()
    stats.stream = stream
    stats.sort_stats("cumulative")
    stats.print_stats(n)
    output = stream.getvalue()

    # Filter to only show pydantic_resolve and resolver-related lines
    lines = output.split("\n")
    in_table = False
    for line in lines:
        if "ncalls" in line and "tottime" in line:
            in_table = True
            print(line)
            continue
        if in_table:
            if line.strip() and not line.startswith("   "):
                break
            if "pydantic_resolve" in line or "resolver" in line or "analysis" in line:
                print(line.rstrip())


def print_summary_stats(stats: pstats.Stats, label: str):
    """Print total call count and time."""
    total_calls = sum(v[0] for v in stats.stats.values())
    total_time = sum(v[3] for v in stats.stats.values())
    print(f"  {label}: {total_calls:,d} total calls, {total_time:.3f}s total cumulative time")


def print_contextvar_analysis(dfs_stats: dict, bfs_stats: dict):
    """Analyze contextvar-related overhead differences."""
    print(f"\n{'=' * 80}")
    print("  ContextVar Overhead Analysis")
    print(f"{'=' * 80}")

    # Look for contextvar-related functions
    contextvar_funcs = [
        k for k in set(dfs_stats.keys()) | set(bfs_stats.keys())
        if "contextvar" in k.lower() or "prepare" in k.lower() or "reset" in k.lower()
    ]

    if contextvar_funcs:
        print(f"\n  {'Function':<55s} {'DFS calls':>10s} {'BFS calls':>10s} {'DFS cum':>10s} {'BFS cum':>10s}")
        print(f"  {'─' * 95}")
        for func in sorted(contextvar_funcs):
            d = dfs_stats.get(func, {"calls": 0, "cumtime": 0})
            b = bfs_stats.get(func, {"calls": 0, "cumtime": 0})
            print(f"  {func:<55s} {d['calls']:>10d} {b['calls']:>10d} {d['cumtime']:>10.3f} {b['cumtime']:>10.3f}")
    else:
        print("  No contextvar-specific functions found in filtered stats.")

    # Count _traverse calls (DFS) vs level iterations (BFS)
    dfs_traverse = sum(v["calls"] for k, v in dfs_stats.items() if "_traverse" in k)
    bfs_traverse = sum(v["calls"] for k, v in bfs_stats.items() if "_bfs_traverse" in k)
    print(f"\n  DFS _traverse calls: {dfs_traverse}")
    print(f"  BFS _bfs_traverse calls: {bfs_traverse}")

    dfs_resolve_field = sum(v["calls"] for k, v in dfs_stats.items() if "_execute_resolve_method_field" in k)
    bfs_resolve_field = sum(v["calls"] for k, v in bfs_stats.items() if "_bfs_do_resolve" in k)
    print(f"  DFS _execute_resolve_method_field calls: {dfs_resolve_field}")
    print(f"  BFS _bfs_do_resolve calls: {bfs_resolve_field}")


def print_primitive_call_analysis(dfs_stats: dict, bfs_stats: dict):
    """Analyze primitive calls that differ."""
    print(f"\n{'=' * 80}")
    print("  Primitive Call Analysis (functions with largest call count difference)")
    print(f"{'=' * 80}")

    diffs = []
    all_keys = set(dfs_stats.keys()) | set(bfs_stats.keys())
    for key in all_keys:
        d = dfs_stats.get(key, {"calls": 0, "cumtime": 0})
        b = bfs_stats.get(key, {"calls": 0, "cumtime": 0})
        delta = b["calls"] - d["calls"]
        if delta != 0:
            diffs.append((key, d["calls"], b["calls"], delta, d["cumtime"], b["cumtime"]))

    diffs.sort(key=lambda x: abs(x[3]), reverse=True)

    print(f"\n  {'Function':<55s} {'DFS':>8s} {'BFS':>8s} {'Δ':>8s} {'DFS cum':>8s} {'BFS cum':>8s}")
    print(f"  {'─' * 95}")
    for key, dc, bc, delta, dct, bct in diffs[:20]:
        print(f"  {key:<55s} {dc:>8d} {bc:>8d} {delta:>+8d} {dct:>8.3f} {bct:>8.3f}")


# ──────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────

def main():
    n_iterations = 30

    print("=" * 80)
    print(f"  cProfile: DFS vs BFS ({n_iterations} iterations, {N_USERS} users)")
    print("  Tree depth: User→Post→Comment (3 levels)")
    print(f"  Nodes: {N_USERS} users, {N_USERS * N_POSTS_PER_USER} posts, {N_USERS * N_POSTS_PER_USER * N_COMMENTS_PER_POST} comments")
    print("=" * 80)

    dfs_stats_obj = profile_mode("dfs", n_iterations)
    bfs_stats_obj = profile_mode("bfs", n_iterations)

    print("\n")
    print_summary_stats(dfs_stats_obj, "DFS")
    print_summary_stats(bfs_stats_obj, "BFS")

    # Filter to pydantic_resolve functions
    dfs_filtered = filter_stats(dfs_stats_obj)
    bfs_filtered = filter_stats(bfs_stats_obj)

    print_comparison(dfs_filtered, bfs_filtered)
    print_contextvar_analysis(dfs_filtered, bfs_filtered)
    print_primitive_call_analysis(dfs_filtered, bfs_filtered)

    # Also print raw top-N for each
    print_top_stats(dfs_stats_obj, "DFS Raw", 40)
    print_top_stats(bfs_stats_obj, "BFS Raw", 40)


if __name__ == "__main__":
    main()
