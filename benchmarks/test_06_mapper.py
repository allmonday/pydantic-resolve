"""
Benchmark 6: Mapper Transformations

测试数据映射和转换性能。

测试场景:
- DTO 到 Domain Model 转换
- Lambda 映射
- 批量数据转换

性能目标: < 1s for 2000 course objects
"""

import time
import asyncio
import pytest
from typing import List
from pydantic import BaseModel

from pydantic_resolve import Resolver, mapper
from .conftest import measure_performance, assert_performance


# ============================================================================
# Test Data Classes
# ============================================================================

class CourseDTO(BaseModel):
    """外部 API 格式"""
    id: int
    title: str
    instructor_id: int


class Course(BaseModel):
    """内部格式"""
    id: int
    name: str
    instructor_id: int


class StudentWithCourses(BaseModel):
    """学生及其课程"""
    id: int
    name: str

    courses: List[Course] = []
    @mapper(lambda items: [
        Course(id=c.id, name=c.title, instructor_id=c.instructor_id)
        for c in items
    ])
    async def resolve_courses(self) -> List[CourseDTO]:
        await asyncio.sleep(0.001)
        return [
            CourseDTO(id=i, title=f'Course {i}', instructor_id=i % 5)
            for i in range(20)
        ]

    course_count: int = 0
    def post_course_count(self):
        return len(self.courses)


class ExternalCourseDTO(BaseModel):
    """外部课程 DTO"""
    id: int
    title: str
    instructor_id: int
    credits: int = 3


class ComplexCourseModel(BaseModel):
    """复杂课程模型"""
    id: int
    name: str
    instructor_id: int
    credits: int


class CourseWithComplexMapper(BaseModel):
    """需要复杂映射的课程"""
    id: int
    name: str
    instructor_id: int

    # 简化：直接转换名称为大写
    display_name: str = ''
    def post_display_name(self):
        return self.name.upper()


# ============================================================================
# Benchmarks
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_mapper_simple_transformation():
    """
    Benchmark: 简单 Mapper 转换

    测试目标:
    - 测试 DTO 到 Domain Model 的转换性能
    - 测量 lambda 映射的开销

    场景:
    - 100 students
    - 每个 student 有 20 courses
    - 总共 2000 次转换

    预期: < 1s
    """
    students = [StudentWithCourses(id=i, name=f'Student {i}') for i in range(100)]

    start = time.perf_counter()
    result = await Resolver().resolve(students)
    elapsed = time.perf_counter() - start

    assert len(result) == 100

    total_courses = sum(s.course_count for s in result)
    assert total_courses == 2000

    measure_performance(result, elapsed, node_count=100, item_count=2000)
    print(f"  🔄 Transformation count: {total_courses}")
    print(f"  📊 Average: {elapsed/total_courses*1000:.3f}ms per transformation")

    assert_performance(elapsed, 1.0, "Mapper simple transformation")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_mapper_large_dataset():
    """
    Benchmark: 大规模 Mapper 转换

    测试目标:
    - 测试大量数据转换的性能
    - 验证 mapper 的可扩展性

    场景:
    - 500 students
    - 每个 student 有 10 courses
    - 总共 5000 次转换

    预期: < 2s
    """

    class StudentWithManyCourses(BaseModel):
        id: int
        name: str

        courses: List[Course] = []
        @mapper(lambda items: [
            Course(id=c.id, name=c.title, instructor_id=c.instructor_id)
            for c in items
        ])
        async def resolve_courses(self) -> List[CourseDTO]:
            await asyncio.sleep(0.001)
            return [
                CourseDTO(id=i, title=f'Course {i}', instructor_id=i % 5)
                for i in range(10)
            ]

    students = [StudentWithManyCourses(id=i, name=f'Student {i}') for i in range(500)]

    start = time.perf_counter()
    result = await Resolver().resolve(students)
    elapsed = time.perf_counter() - start

    assert len(result) == 500

    total_courses = sum(len(s.courses) for s in result)
    assert total_courses == 5000

    measure_performance(result, elapsed, node_count=500, item_count=5000)
    print(f"  🔄 Transformation count: {total_courses}")

    assert_performance(elapsed, 2.0, "Mapper large dataset")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_mapper_no_transformation():
    """
    Benchmark: 不使用 Mapper 的对比测试

    测试目标:
    - 测试没有 mapper 时的性能
    - 作为基准对比

    场景:
    - 100 students
    - 直接返回 Course，不需要转换

    预期: < 0.5s (应该比 mapper 快)
    """

    class StudentDirect(BaseModel):
        id: int
        name: str

        courses: List[CourseDTO] = []
        async def resolve_courses(self) -> List[CourseDTO]:
            await asyncio.sleep(0.001)
            return [
                CourseDTO(id=i, title=f'Course {i}', instructor_id=i % 5)
                for i in range(20)
            ]

    students = [StudentDirect(id=i, name=f'Student {i}') for i in range(100)]

    start = time.perf_counter()
    result = await Resolver().resolve(students)
    elapsed = time.perf_counter() - start

    assert len(result) == 100

    total_courses = sum(len(s.courses) for s in result)
    assert total_courses == 2000

    measure_performance(result, elapsed, node_count=100, item_count=2000)
    print("  ⚡ No transformation overhead")

    assert_performance(elapsed, 0.5, "No mapper baseline")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_mapper_complex_transformation():
    """
    Benchmark: 复杂 Mapper 转换

    测试目标:
    - 测试复杂映射逻辑的性能
    - 包含多个字段转换和默认值处理

    场景:
    - 100 courses
    - 复杂的映射逻辑

    预期: < 0.5s
    """
    courses = [
        CourseWithComplexMapper(
            id=i,
            name=f'Course {i}',
            instructor_id=i % 5
        )
        for i in range(100)
    ]

    start = time.perf_counter()
    result = await Resolver().resolve(courses)
    elapsed = time.perf_counter() - start

    assert len(result) == 100
    assert all(c.display_name.isupper() for c in result)  # 验证转换生效

    measure_performance(result, elapsed, node_count=100)
    print(f"  🔄 Complex transformations: {len(result)}")

    assert_performance(elapsed, 0.5, "Mapper complex transformation")
