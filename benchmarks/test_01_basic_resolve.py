import asyncio
from typing import List
from pydantic import BaseModel

from pydantic_resolve import Resolver


# ============================================================================
# Test Data Classes
# ============================================================================

class SyncStudent(BaseModel):
    id: int
    name: str

    display_name: str = ''
    def resolve_display_name(self) -> str:
        return f'Student: {self.name}'


class AsyncStudent(BaseModel):
    id: int
    name: str

    courses: List[str] = []
    async def resolve_courses(self) -> List[str]:
        await asyncio.sleep(0.001)
        return ['Math', 'Science', 'History']


def test_sync_resolve(benchmark):
    students = [SyncStudent(id=i, name=f'Student {i}') for i in range(100)]

    def sync_resolve():
        return asyncio.run(Resolver().resolve(students))

    benchmark(sync_resolve)


def test_async_resolve(benchmark):
    students = [AsyncStudent(id=i, name=f'Student {i}') for i in range(100)]

    def sync_resolve():
        return asyncio.run(Resolver().resolve(students))

    benchmark(sync_resolve)


def test_basic_resolve_large_dataset(benchmark):
    students = [AsyncStudent(id=i, name=f'Student {i}') for i in range(1000)]

    def sync_resolve():
        return asyncio.run(Resolver().resolve(students))

    benchmark(sync_resolve)
