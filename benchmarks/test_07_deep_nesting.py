"""
Benchmark 7: Deep Nesting

测试深度嵌套结构的解析性能。

测试场景:
- 递归结构解析
- 深度优先遍历
- 分支因子控制

性能目标: < 1s for ~364 nodes, depth 5, branching factor 3
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

class Node(BaseModel):
    """递归树节点"""
    id: int
    level: int

    children: List['Node'] = []
    async def resolve_children(self) -> List['Node']:
        if self.level >= 5:  # 最大深度
            return []
        await asyncio.sleep(0.0001)
        return [
            Node(
                id=i,
                level=self.level + 1
            )
            for i in range(3)  # 分支因子
        ]

    descendant_count: int = 0
    def post_descendant_count(self):
        return 1 + sum(child.descendant_count for child in self.children)

    level_str: str = ''
    def post_level_str(self):
        return f'Level {self.level}'


# 更新前向引用
Node.model_rebuild()


# ============================================================================
# Benchmarks
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_deep_nesting_standard():
    """
    Benchmark: 标准深度嵌套

    测试目标:
    - 测试递归结构的解析性能
    - 验证深度优先遍历效率

    场景:
    - 深度: 5
    - 分支因子: 3
    - 总节点数: 1 + 3 + 9 + 27 + 81 + 243 = 364

    预期: < 1s
    """
    root = Node(id=0, level=0)

    start = time.perf_counter()
    result = await Resolver().resolve(root)
    elapsed = time.perf_counter() - start

    expected_nodes = sum(3**i for i in range(6))  # 364 nodes
    assert result.descendant_count == expected_nodes

    measure_performance(result, elapsed, node_count=expected_nodes)
    print(f"  🌳 Depth: {5}")
    print(f"  📊 Branching factor: {3}")
    print(f"  📈 Average: {elapsed/expected_nodes*1000:.3f}ms per node")

    assert_performance(elapsed, 1.0, "Deep nesting standard")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_deep_nesting_wide():
    """
    Benchmark: 宽而浅的嵌套

    测试目标:
    - 测试大分支因子的性能
    - 验证广度优先的场景

    场景:
    - 深度: 3
    - 分支因子: 10
    - 总节点数: 1 + 10 + 100 + 1000 = 1111

    预期: < 2s
    """

    class WideNode(BaseModel):
        id: int
        level: int

        children: List['WideNode'] = []
        async def resolve_children(self) -> List['WideNode']:
            if self.level >= 3:
                return []
            await asyncio.sleep(0.0001)
            return [
                WideNode(id=i, level=self.level + 1)
                for i in range(10)
            ]

        descendant_count: int = 0
        def post_descendant_count(self):
            return 1 + sum(child.descendant_count for child in self.children)

    WideNode.model_rebuild()

    root = WideNode(id=0, level=0)

    start = time.perf_counter()
    result = await Resolver().resolve(root)
    elapsed = time.perf_counter() - start

    expected_nodes = sum(10**i for i in range(4))  # 1111 nodes
    assert result.descendant_count == expected_nodes

    measure_performance(result, elapsed, node_count=expected_nodes)
    print(f"  🌳 Depth: {3}")
    print(f"  📊 Branching factor: {10}")
    print("  📈 Width-first traversal")

    assert_performance(elapsed, 2.0, "Deep nesting wide")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_deep_nesting_narrow():
    """
    Benchmark: 窄而深的嵌套

    测试目标:
    - 测试深而窄的分支
    - 验证深度优先场景

    场景:
    - 深度: 8
    - 分支因子: 2
    - 总节点数: 2^9 - 1 = 511

    预期: < 1s
    """

    class NarrowNode(BaseModel):
        id: int
        level: int

        children: List['NarrowNode'] = []
        async def resolve_children(self) -> List['NarrowNode']:
            if self.level >= 8:
                return []
            await asyncio.sleep(0.0001)
            return [
                NarrowNode(id=i, level=self.level + 1)
                for i in range(2)
            ]

        descendant_count: int = 0
        def post_descendant_count(self):
            return 1 + sum(child.descendant_count for child in self.children)

    NarrowNode.model_rebuild()

    root = NarrowNode(id=0, level=0)

    start = time.perf_counter()
    result = await Resolver().resolve(root)
    elapsed = time.perf_counter() - start

    expected_nodes = 2**9 - 1  # 511 nodes
    assert result.descendant_count == expected_nodes

    measure_performance(result, elapsed, node_count=expected_nodes)
    print(f"  🌳 Depth: {8}")
    print(f"  📊 Branching factor: {2}")
    print("  📈 Depth-first traversal")

    assert_performance(elapsed, 1.0, "Deep nesting narrow")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_deep_nesting_with_post_calculations():
    """
    Benchmark: 深度嵌套 + Post 计算

    测试目标:
    - 测试嵌套结构中的 post 方法
    - 验证层级计算的性能

    预期: < 1.5s for 364 nodes with calculations
    """
    root = Node(id=0, level=0)

    start = time.perf_counter()
    result = await Resolver().resolve(root)
    elapsed = time.perf_counter() - start

    # 验证 post 方法执行
    assert result.level_str == 'Level 0'

    # 验证所有节点都有 level_str
    def count_nodes_with_level(node):
        count = 1
        for child in node.children:
            count += count_nodes_with_level(child)
        return count

    total_nodes = count_nodes_with_level(result)
    assert total_nodes == 364

    measure_performance(result, elapsed, node_count=total_nodes)
    print(f"  🌳 Depth: {5} with post calculations")

    assert_performance(elapsed, 1.5, "Deep nesting with post")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_deep_nesting_multiple_roots():
    """
    Benchmark: 多个深嵌套根节点

    测试目标:
    - 测试多个独立树的处理
    - 验证并行处理效率

    场景:
    - 10 个根节点
    - 每个根节点: depth 3, branching 3
    - 总节点: 10 * (1 + 3 + 9 + 27) = 400

    预期: < 1s
    """
    # 定义一个深度限制为 3 的 Node 类
    class ShallowNode(BaseModel):
        id: int
        level: int

        children: List['ShallowNode'] = []
        async def resolve_children(self) -> List['ShallowNode']:
            if self.level >= 3:  # 深度限制为 3
                return []
            await asyncio.sleep(0.0001)
            return [
                ShallowNode(
                    id=i,
                    level=self.level + 1
                )
                for i in range(3)
            ]

        descendant_count: int = 0
        def post_descendant_count(self):
            return 1 + sum(child.descendant_count for child in self.children)

    ShallowNode.model_rebuild()

    roots = [ShallowNode(id=i, level=0) for i in range(10)]

    start = time.perf_counter()
    result = await Resolver().resolve(roots)
    elapsed = time.perf_counter() - start

    assert len(result) == 10

    total_descendants = sum(r.descendant_count - 1 for r in result)  # -1 排除根节点本身
    total_nodes = len(result) + total_descendants

    expected_per_tree = sum(3**i for i in range(4))  # 40 nodes per tree
    assert total_nodes == 10 * expected_per_tree

    measure_performance(result, elapsed, node_count=10, item_count=total_nodes)
    print(f"  🌳 {len(result)} trees, depth 3 each")

    assert_performance(elapsed, 1.0, "Multiple deep trees")
