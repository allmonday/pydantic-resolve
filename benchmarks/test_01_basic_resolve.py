"""
Benchmark 1: Basic Resolve Methods

测试基础的 resolve 方法性能，包括同步和异步方法。

测试场景:
- 同步 resolve 方法
- 异步 resolve 方法
- 字段计算和转换

性能目标: < 0.5s for 100 students
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

class SimpleStudent(BaseModel):
    """简单的学生模型"""
    id: int
    name: str

    display_name: str = ''
    def resolve_display_name(self) -> str:
        return f'Student: {self.name}'

    courses: List[str] = []
    async def resolve_courses(self) -> List[str]:
        await asyncio.sleep(0.001)
        return ['Math', 'Science', 'History']


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_basic_resolve_sync():
    """
    Benchmark: 基础同步 resolve 方法

    测试目标:
    - 测量同步 resolve 方法的性能
    - 验证字段计算的开销

    预期: < 0.01s for 100 students
    """
    students = [SimpleStudent(id=i, name=f'Student {i}') for i in range(100)]

    start = time.perf_counter()
    result = await Resolver().resolve(students)
    elapsed = time.perf_counter() - start

    assert len(result) == 100
    assert all(s.display_name.startswith('Student:') for s in result)

    measure_performance(result, elapsed, node_count=100)
    assert_performance(elapsed, 0.5, "Basic resolve sync")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_basic_resolve_async():
    """
    Benchmark: 基础异步 resolve 方法

    测试目标:
    - 测量异步 resolve 方法的性能
    - 验证 async/await 的开销

    预期: < 0.5s for 100 students
    """
    students = [SimpleStudent(id=i, name=f'Student {i}') for i in range(100)]

    start = time.perf_counter()
    result = await Resolver().resolve(students)
    elapsed = time.perf_counter() - start

    assert len(result) == 100
    assert all(len(s.courses) == 3 for s in result)

    measure_performance(result, elapsed, node_count=100)
    assert_performance(elapsed, 0.5, "Basic resolve async")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_basic_resolve_mixed():
    """
    Benchmark: 混合同步和异步 resolve 方法

    测试目标:
    - 测量同时使用同步和异步方法的性能
    - 验证混合场景的开销

    预期: < 0.5s for 100 students
    """
    students = [SimpleStudent(id=i, name=f'Student {i}') for i in range(100)]

    start = time.perf_counter()
    result = await Resolver().resolve(students)
    elapsed = time.perf_counter() - start

    assert len(result) == 100
    assert all(s.display_name.startswith('Student:') for s in result)
    assert all(len(s.courses) == 3 for s in result)

    measure_performance(result, elapsed, node_count=100)
    assert_performance(elapsed, 0.5, "Basic resolve mixed")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_basic_resolve_large_dataset():
    """
    Benchmark: 大数据集的基础解析

    测试目标:
    - 测试可扩展性
    - 验证大批量数据的性能

    预期: < 2s for 1000 students
    """
    students = [SimpleStudent(id=i, name=f'Student {i}') for i in range(1000)]

    start = time.perf_counter()
    result = await Resolver().resolve(students)
    elapsed = time.perf_counter() - start

    assert len(result) == 1000
    assert all(s.display_name.startswith('Student:') for s in result)

    measure_performance(result, elapsed, node_count=1000)
    assert_performance(elapsed, 2.0, "Basic resolve large dataset")
