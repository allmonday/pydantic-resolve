"""
Benchmark 8: Large Datasets

测试大数据集处理的性能和可扩展性。

测试场景:
- 1000+ 对象处理
- 递归关联加载
- 内存使用情况

性能目标: < 2s for 1000 products with 3 related each
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

class RelatedProduct(BaseModel):
    """相关产品 - 不带递归解析"""
    id: int
    name: str
    category: str
    price: float = 0.0


class Product(BaseModel):
    """产品 - 带关联产品"""
    id: int
    name: str
    category: str
    price: float = 0.0

    related_products: List[RelatedProduct] = []
    async def resolve_related_products(self) -> List[RelatedProduct]:
        # 模拟少量相关产品
        await asyncio.sleep(0.001)
        return [
            RelatedProduct(
                id=i,
                name=f'Related {i}',
                category=f'Cat {i % 10}',
                price=float(i * 10)
            )
            for i in range(3)
        ]


class LargeItem(BaseModel):
    """大批量项"""
    id: int
    value: int

    calculated: int = 0
    def post_calculated(self):
        return self.value * 2


# ============================================================================
# Benchmarks
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_large_dataset_basic():
    """
    Benchmark: 基础大数据集

    测试目标:
    - 测试 1000+ 对象的解析性能
    - 验证可扩展性

    场景:
    - 1000 products
    - 每个 product 有 3 related products
    - 总节点: 1000 + 3000 = 4000

    预期: < 2s
    """
    products = [
        Product(
            id=i,
            name=f'Product {i}',
            category=f'Cat {i % 10}',
            price=float(i * 10)
        )
        for i in range(1000)
    ]

    start = time.perf_counter()
    result = await Resolver().resolve(products)
    elapsed = time.perf_counter() - start

    assert len(result) == 1000

    # 计算总节点数 (根节点 + 第一层相关产品)
    total_nodes = len(result) + sum(len(p.related_products) for p in result)
    assert total_nodes == 4000

    measure_performance(result, elapsed, node_count=1000, item_count=total_nodes)
    print(f"  📦 Total objects resolved: {total_nodes}")
    print(f"  📈 Average: {elapsed/total_nodes*1000:.3f}ms per object")

    assert_performance(elapsed, 2.0, "Large dataset basic")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_large_dataset_with_post():
    """
    Benchmark: 大数据集 + Post 计算

    测试目标:
    - 测试大量对象的计算开销
    - 验证 post 方法在大数据集上的性能

    场景:
    - 2000 items
    - 每个都有 post 计算

    预期: < 1s
    """
    items = [LargeItem(id=i, value=i) for i in range(2000)]

    start = time.perf_counter()
    result = await Resolver().resolve(items)
    elapsed = time.perf_counter() - start

    assert len(result) == 2000
    assert all(i.calculated == i.value * 2 for i in result)

    measure_performance(result, elapsed, node_count=2000)

    assert_performance(elapsed, 1.0, "Large dataset with post")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_very_large_dataset():
    """
    Benchmark: 超大数据集

    测试目标:
    - 测试极端情况的性能
    - 确定性能瓶颈

    场景:
    - 5000 items

    预期: < 5s (可以接受，但应该优化)
    """
    items = [LargeItem(id=i, value=i) for i in range(5000)]

    start = time.perf_counter()
    result = await Resolver().resolve(items)
    elapsed = time.perf_counter() - start

    assert len(result) == 5000

    measure_performance(result, elapsed, node_count=5000)
    print("  ⚠️  Large dataset test")

    # 放宽性能要求
    assert_performance(elapsed, 5.0, "Very large dataset")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_large_dataset_list_input():
    """
    Benchmark: 列表输入的大数据集

    测试目标:
    - 测试从列表开始的解析
    - 验证 list 和单对象性能差异

    预期: < 2s for 1000 products
    """
    products = [
        Product(
            id=i,
            name=f'Product {i}',
            category=f'Cat {i % 10}',
            price=float(i * 10)
        )
        for i in range(1000)
    ]

    start = time.perf_counter()
    result = await Resolver().resolve(products)  # list input
    elapsed = time.perf_counter() - start

    assert len(result) == 1000

    total_nodes = len(result) + sum(len(p.related_products) for p in result)
    measure_performance(result, elapsed, node_count=1000, item_count=total_nodes)

    assert_performance(elapsed, 2.0, "Large dataset list input")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_large_dataset_simple_objects():
    """
    Benchmark: 大量简单对象

    测试目标:
    - 测试没有关联的简单对象性能
    - 确定基础开销

    预期: < 1s for 10000 simple objects
    """

    class SimpleProduct(BaseModel):
        id: int
        name: str
        price: float

    products = [
        SimpleProduct(id=i, name=f'Product {i}', price=float(i))
        for i in range(10000)
    ]

    start = time.perf_counter()
    result = await Resolver().resolve(products)
    elapsed = time.perf_counter() - start

    assert len(result) == 10000

    measure_performance(result, elapsed, node_count=10000)
    print(f"  📊 Throughput: {len(result)/elapsed:.0f} objects/second")

    assert_performance(elapsed, 1.0, "Large simple objects")
