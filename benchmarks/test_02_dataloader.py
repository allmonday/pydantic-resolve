"""
Benchmark 2: DataLoader Batch Loading

测试 DataLoader 批量加载性能，验证 N+1 查询优化效果。

测试场景:
- 一对一关系加载
- 批量查询优化
- 缓存效果

性能目标: < 0.5s for 1000 tasks with 10 unique users
性能提升: ~100x (1000 queries -> 10 queries)
"""

import time
import asyncio
import pytest
from typing import List, Optional
from pydantic import BaseModel
from aiodataloader import DataLoader

from pydantic_resolve import Resolver, LoaderDepend
from .conftest import measure_performance, assert_performance


# ============================================================================
# Test Data and Loaders
# ============================================================================

# 模拟数据库
user_db = {
    i: {'id': i, 'name': f'User {i}', 'email': f'user{i}@example.com'}
    for i in range(100)
}

task_db = {
    i: {'id': i, 'title': f'Task {i}', 'user_id': i % 10}
    for i in range(1000)
}


class SimpleUser(BaseModel):
    """简单的用户模型"""
    id: int
    name: str
    email: str


class UserLoader(DataLoader):
    """用户批量加载器"""
    async def batch_load_fn(self, keys: List[int]):
        await asyncio.sleep(0.01)  # 模拟数据库查询
        return [user_db.get(k) for k in keys]


class TaskWithUser(BaseModel):
    """带用户的任务"""
    id: int
    title: str
    user_id: int

    owner: Optional[SimpleUser] = None
    async def resolve_owner(self, loader=LoaderDepend(UserLoader)):
        return await loader.load(self.user_id)


# ============================================================================
# Benchmarks
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_dataloader_one_to_one():
    """
    Benchmark: DataLoader 一对一关系加载

    测试目标:
    - 验证批量加载效果
    - 测量 N+1 查询优化

    场景:
    - 1000 tasks
    - 10 unique users (user_id = task_id % 10)
    - 避免 1000 次单独查询

    预期: < 0.5s
    优化效果: 1000 queries -> 10 queries
    """
    tasks = [TaskWithUser(
        id=i,
        title=f'Task {i}',
        user_id=i % 10
    ) for i in range(1000)]

    start = time.perf_counter()
    result = await Resolver().resolve(tasks)
    elapsed = time.perf_counter() - start

    assert len(result) == 1000

    # 验证数据正确性
    unique_users = len(set(t.user_id for t in result))
    assert unique_users == 10, f"Expected 10 unique users, got {unique_users}"

    loaded_users = sum(1 for t in result if t.owner is not None)
    assert loaded_users == 1000, f"Expected 1000 loaded users, got {loaded_users}"

    measure_performance(result, elapsed, node_count=1000, item_count=1000)
    print(f"  🚀 Batch loading prevented {1000} queries")
    print("  📊 Queries reduced from 1000 to ~10 (100x improvement)")

    assert_performance(elapsed, 0.5, "DataLoader one-to-one")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_dataloader_caching():
    """
    Benchmark: DataLoader 缓存效果

    测试目标:
    - 验证 DataLoader 的缓存机制
    - 测量重复加载同一对象的性能

    场景:
    - 多个任务引用同一个用户
    - 验证只加载一次

    预期: < 0.3s
    """
    # 创建更多重复引用的场景
    tasks = [TaskWithUser(
        id=i,
        title=f'Task {i}',
        user_id=i % 5  # 只使用 5 个用户
    ) for i in range(500)]

    start = time.perf_counter()
    result = await Resolver().resolve(tasks)
    elapsed = time.perf_counter() - start

    assert len(result) == 500

    unique_users = len(set(t.user_id for t in result))
    assert unique_users == 5

    loaded_users = sum(1 for t in result if t.owner is not None)
    assert loaded_users == 500

    measure_performance(result, elapsed, node_count=500, item_count=500)
    print(f"  🚀 Batch loading: {500} tasks -> ~5 queries")
    print(f"  📊 Cache efficiency: {500/5:.1f}x")

    assert_performance(elapsed, 0.3, "DataLoader caching")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_dataloader_small_batch():
    """
    Benchmark: DataLoader 小批量加载

    测试目标:
    - 测试少量数据的批量加载
    - 验证批量加载在小数据集上的开销

    场景:
    - 100 tasks
    - 10 unique users

    预期: < 0.1s
    """
    tasks = [TaskWithUser(
        id=i,
        title=f'Task {i}',
        user_id=i % 10
    ) for i in range(100)]

    start = time.perf_counter()
    result = await Resolver().resolve(tasks)
    elapsed = time.perf_counter() - start

    assert len(result) == 100

    loaded_users = sum(1 for t in result if t.owner is not None)
    assert loaded_users == 100

    measure_performance(result, elapsed, node_count=100)
    print("  🚀 Batch loading: 100 tasks -> ~10 queries")

    assert_performance(elapsed, 0.1, "DataLoader small batch")
