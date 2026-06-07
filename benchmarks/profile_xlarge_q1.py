"""Micro-profile: identify which BFS functions cause overhead at XLarge scale.

Compares per-function time for Q1 (1-level, 2500 tasks) where BFS regresses.

Usage:
    uv run python benchmarks/profile_xlarge_q1.py
"""

import asyncio
import cProfile
import pstats

from pydantic import BaseModel
from pydantic_resolve import Loader, Resolver, build_object

# ──────────────────────────────────────────────────────────
# Flat Q1 scenario: 2500 tasks → owner
# ──────────────────────────────────────────────────────────

N_TASKS = 2500
USERS = {i: {"id": i, "name": f"User_{i}"} for i in range(1, 101)}

async def user_loader(user_ids):
    users = [USERS.get(uid) for uid in user_ids]
    return build_object(users, user_ids, lambda u: u["id"])

class UserView(BaseModel):
    id: int
    name: str

class TaskView(BaseModel):
    id: int
    title: str
    owner_id: int
    owner: UserView | None = None
    def resolve_owner(self, loader=Loader(user_loader)):
        return loader.load(self.owner_id)


async def run_mode(mode, n_iters=10):
    for _ in range(n_iters):
        tasks = [TaskView(id=i, title=f"Task_{i}", owner_id=(i % 100) + 1) for i in range(N_TASKS)]
        await Resolver(mode=mode).resolve(tasks)


def profile_mode(mode):
    pr = cProfile.Profile()
    pr.enable()
    asyncio.run(run_mode(mode, n_iters=10))
    pr.disable()
    return pr


def main():
    print("=" * 90)
    print(f"  Micro-profile: Q1 (1-level, {N_TASKS} tasks) — DFS vs BFS")
    print("=" * 90)

    for mode in ["dfs", "bfs"]:
        pr = profile_mode(mode)
        stats = pstats.Stats(pr)
        stats.sort_stats("cumulative")

        print(f"\n  {mode.upper()} — resolver.py functions only:")
        print(f"  {'Function':<50s} {'calls':>8s} {'tottime':>8s} {'cumtime':>8s}")
        print(f"  {'─' * 76}")

        # Filter to resolver.py
        for (filename, line, func), (cc, nc, tt, ct, callers) in stats.stats.items():
            if "resolver.py" in filename and ct > 0.001:
                print(f"  {func:<50s} L{line:<4d} {nc:>8d} {tt:>8.3f} {ct:>8.3f}")

        # Total
        total = sum(v[3] for v in stats.stats.values())
        print(f"\n  Total cumulative: {total:.3f}s")


if __name__ == "__main__":
    main()
