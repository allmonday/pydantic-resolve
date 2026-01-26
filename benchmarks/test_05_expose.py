"""
Benchmark 5: Expose Pattern

测试父节点向子节点暴露数据的性能。

测试场景:
- 父节点数据暴露
- 子节点访问祖先数据
- 上下文传播

性能目标: < 1s for 20 roots, 200 children, 1000 grandchildren
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

class GrandChildEx(BaseModel):
    """孙节点"""
    id: int
    name: str

    # 访问祖先节点的数据
    root_name: str = ''
    def post_root_name(self, ancestor_context):
        name = ancestor_context.get('root_name', '')
        return str(name) if name else ''

    parent_id: str = ''
    def post_parent_id(self, ancestor_context):
        parent_id = ancestor_context.get('parent_path')
        return str(parent_id) if parent_id is not None else ''


class ChildEx(BaseModel):
    """子节点"""
    __pydantic_resolve_expose__ = {
        'id': 'parent_path'
    }

    id: int
    name: str

    grand_children: List[GrandChildEx] = []
    async def resolve_grand_children(self) -> List[GrandChildEx]:
        await asyncio.sleep(0.001)
        return [GrandChildEx(id=i, name=f'GrandChild {i}') for i in range(5)]


class RootEx(BaseModel):
    """根节点"""
    __pydantic_resolve_expose__ = {
        'name': 'root_name'
    }

    id: int
    name: str

    children: List[ChildEx] = []
    async def resolve_children(self) -> List[ChildEx]:
        await asyncio.sleep(0.001)
        return [ChildEx(id=i, name=f'Child {i}') for i in range(10)]


# ============================================================================
# Benchmarks
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_expose_three_levels():
    """
    Benchmark: 三级 Expose 模式

    测试目标:
    - 测试跨层数据暴露的性能
    - 验证 ancestor_context 的开销

    场景:
    - 20 roots
    - 每个 root 有 10 children
    - 每个 child 有 5 grandchildren
    - 总节点: 20 + 200 + 1000 = 1220

    数据流:
    Root.name -> 暴露为 root_name -> GrandChild 可访问
    Child.id -> 暴露为 parent_path -> GrandChild 可访问

    预期: < 1s
    """
    roots = [RootEx(id=i, name=f'Root {i}') for i in range(20)]

    start = time.perf_counter()
    result = await Resolver().resolve(roots)
    elapsed = time.perf_counter() - start

    assert len(result) == 20

    # 验证数据正确传播
    total_nodes = len(result)
    for root in result:
        total_nodes += len(root.children)
        assert len(root.children) == 10

        for child in root.children:
            total_nodes += len(child.grand_children)
            assert len(child.grand_children) == 5

            # 验证孙节点可以访问祖先数据
            for grand_child in child.grand_children:
                assert grand_child.root_name == root.name
                assert grand_child.parent_id == str(child.id)

    measure_performance(result, elapsed, node_count=20, item_count=total_nodes)
    print("  🌲 Depth: 3 levels")
    print(f"  📊 Context propagation: {total_nodes} nodes")

    assert_performance(elapsed, 1.0, "Expose three levels")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_expose_two_levels():
    """
    Benchmark: 两级 Expose 模式

    测试目标:
    - 测试简单的父子关系暴露
    - 验证性能随深度减少而改善

    场景:
    - 50 roots
    - 每个 root 有 10 children

    预期: < 0.5s
    """

    class ChildEx(BaseModel):
        id: int
        name: str

        parent_name: str = ''
        def post_parent_name(self, ancestor_context):
            return ancestor_context.get('parent_name', '')

    class ParentEx(BaseModel):
        __pydantic_resolve_expose__ = {
            'name': 'parent_name'
        }
        id: int
        name: str

        children: List[ChildEx] = []
        async def resolve_children(self) -> List[ChildEx]:
            await asyncio.sleep(0.001)
            return [ChildEx(id=i, name=f'Child {i}') for i in range(5)]

    roots = [ParentEx(id=i, name=f'Parent {i}') for i in range(50)]

    start = time.perf_counter()
    result = await Resolver().resolve(roots)
    elapsed = time.perf_counter() - start

    assert len(result) == 50
    assert all(len(r.children) == 5 for r in result)

    total_nodes = len(result) + sum(len(r.children) for r in result)
    measure_performance(result, elapsed, node_count=50, item_count=total_nodes)
    print(f"  📊 Context propagation: {total_nodes} nodes (2 levels)")

    assert_performance(elapsed, 0.5, "Expose two levels")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_expose_no_context():
    """
    Benchmark: 没有 Expose 的对比测试

    测试目标:
    - 测试不使用 Expose 的性能
    - 作为基准对比

    预期: < 0.5s (应该比 expose 快一点)
    """

    class ChildNoEx(BaseModel):
        id: int
        name: str

    class ParentNoEx(BaseModel):
        id: int
        name: str

        children: List[ChildNoEx] = []
        async def resolve_children(self) -> List[ChildNoEx]:
            await asyncio.sleep(0.001)
            return [ChildNoEx(id=i, name=f'Child {i}') for i in range(5)]

    roots = [ParentNoEx(id=i, name=f'Parent {i}') for i in range(50)]

    start = time.perf_counter()
    result = await Resolver().resolve(roots)
    elapsed = time.perf_counter() - start

    assert len(result) == 50

    total_nodes = len(result) + sum(len(r.children) for r in result)
    measure_performance(result, elapsed, node_count=50, item_count=total_nodes)
    print(f"  📊 No context overhead: {total_nodes} nodes")

    assert_performance(elapsed, 0.5, "No expose baseline")
