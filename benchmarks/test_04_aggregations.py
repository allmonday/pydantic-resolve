"""
Benchmark 4: Data Aggregations

测试层级数据聚合和 post 方法链式计算性能。

测试场景:
- 多层级聚合
- 从子节点收集数据
- 计算统计信息

性能目标: < 1s for 50 blogs with 500 posts
"""

import time
import asyncio
import pytest
from typing import List
from pydantic import BaseModel

from pydantic_resolve import Resolver
from .conftest import measure_performance, assert_performance


# ============================================================================
# Test Data Classes
# ============================================================================

class MyComment(BaseModel):
    """评论"""
    id: int
    text: str
    likes: int = 0


class MyPost(BaseModel):
    """文章"""
    id: int
    title: str

    my_comments: List[MyComment] = []
    async def resolve_my_comments(self) -> List[MyComment]:
        await asyncio.sleep(0.001)
        return [
            MyComment(id=1, text='Great!', likes=5),
            MyComment(id=2, text='Thanks!', likes=3),
        ]

    comment_likes: int = 0
    def post_comment_likes(self):
        return sum(c.likes for c in self.my_comments)

    comment_count: int = 0
    def post_comment_count(self):
        return len(self.my_comments)


class MyBlog(BaseModel):
    """博客"""
    id: int
    title: str

    my_posts: List[MyPost] = []
    async def resolve_my_posts(self) -> List[MyPost]:
        await asyncio.sleep(0.001)
        return [MyPost(id=i, title=f'Post {i}') for i in range(10)]

    total_likes: int = 0
    def post_total_likes(self):
        return sum(p.comment_likes for p in self.my_posts)

    total_comments: int = 0
    def post_total_comments(self):
        return sum(p.comment_count for p in self.my_posts)

    posts_count: int = 0
    def post_posts_count(self):
        return len(self.my_posts)

    avg_likes_per_post: float = 0.0
    def post_avg_likes_per_post(self):
        # 直接计算，避免依赖其他 post 字段的执行顺序
        count = len(self.my_posts)
        if count > 0:
            total = sum(p.comment_likes for p in self.my_posts)
            return total / count
        return 0.0


# ============================================================================
# Benchmarks
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_aggregation_two_levels():
    """
    Benchmark: 两层聚合

    测试目标:
    - Blog -> Post 聚合
    - 计算 total_likes, total_comments

    场景:
    - 50 blogs
    - 每个 blog 有 10 posts
    - 每个 post 有 2 comments

    预期: < 1s
    总节点: 50 blogs + 500 posts + 1000 comments = 1550
    """
    blogs = [MyBlog(id=i, title=f'Blog {i}') for i in range(50)]

    start = time.perf_counter()
    result = await Resolver().resolve(blogs)
    elapsed = time.perf_counter() - start

    assert len(result) == 50

    # 验证聚合结果
    assert all(b.posts_count == 10 for b in result)
    assert all(b.total_likes == 80 for b in result)  # 10 posts * 2 comments * (5+3) likes
    assert all(b.total_comments == 20 for b in result)  # 10 posts * 2 comments

    total_likes = sum(b.total_likes for b in result)
    total_comments = sum(b.total_comments for b in result)

    measure_performance(result, elapsed, node_count=50, item_count=1550)
    print(f"  📊 Total likes aggregated: {total_likes}")
    print(f"  📊 Total comments aggregated: {total_comments}")

    assert_performance(elapsed, 1.0, "Two-level aggregation")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_aggregation_with_average():
    """
    Benchmark: 聚合 + 平均值计算

    测试目标:
    - 测试包含除法的聚合计算
    - 验证统计函数的性能

    预期: < 1s for 50 blogs
    """
    blogs = [MyBlog(id=i, title=f'Blog {i}') for i in range(50)]

    start = time.perf_counter()
    result = await Resolver().resolve(blogs)
    elapsed = time.perf_counter() - start

    assert len(result) == 50
    assert all(b.avg_likes_per_post == 8.0 for b in result)  # 80 likes / 10 posts

    measure_performance(result, elapsed, node_count=50)

    assert_performance(elapsed, 1.0, "Aggregation with average")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_aggregation_small_scale():
    """
    Benchmark: 小规模聚合

    测试目标:
    - 测试小数据集的聚合性能
    - 验证聚合在小数据集上的开销

    场景:
    - 10 blogs
    - 每个 blog 有 10 posts

    预期: < 0.1s
    """
    blogs = [MyBlog(id=i, title=f'Blog {i}') for i in range(10)]

    start = time.perf_counter()
    result = await Resolver().resolve(blogs)
    elapsed = time.perf_counter() - start

    assert len(result) == 10
    assert all(b.posts_count == 10 for b in result)

    measure_performance(result, elapsed, node_count=10)

    assert_performance(elapsed, 0.1, "Small-scale aggregation")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_aggregation_large_scale():
    """
    Benchmark: 大规模聚合

    测试目标:
    - 测试大数据集的聚合性能
    - 验证可扩展性

    场景:
    - 100 blogs
    - 每个 blog 有 10 posts

    预期: < 2s
    """
    blogs = [MyBlog(id=i, title=f'Blog {i}') for i in range(100)]

    start = time.perf_counter()
    result = await Resolver().resolve(blogs)
    elapsed = time.perf_counter() - start

    assert len(result) == 100
    assert all(b.posts_count == 10 for b in result)

    total_likes = sum(b.total_likes for b in result)
    measure_performance(result, elapsed, node_count=100)
    print(f"  📊 Total likes aggregated: {total_likes}")

    assert_performance(elapsed, 2.0, "Large-scale aggregation")
