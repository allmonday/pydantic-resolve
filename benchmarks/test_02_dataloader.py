import asyncio
from typing import List, Optional
from pydantic import BaseModel
from aiodataloader import DataLoader

from pydantic_resolve import Resolver, LoaderDepend

# ============================================================================
# Test Data and Loaders
# ============================================================================

user_db = {
    i: {'id': i, 'name': f'User {i}', 'email': f'user{i}@example.com'}
    for i in range(100)
}

task_db = {
    i: {'id': i, 'title': f'Task {i}', 'user_id': i % 10}
    for i in range(1000)
}

class SimpleUser(BaseModel):
    id: int
    name: str
    email: str

class UserLoader(DataLoader):
    async def batch_load_fn(self, keys: List[int]):
        await asyncio.sleep(0.01)  # 模拟数据库查询
        return [user_db.get(k) for k in keys]

class TaskWithUser(BaseModel):
    id: int
    title: str
    user_id: int

    owner: Optional[SimpleUser] = None
    async def resolve_owner(self, loader=LoaderDepend(UserLoader)):
        return await loader.load(self.user_id)

# ============================================================================
# Benchmarks
# ============================================================================

def test_dataloader(benchmark):
    tasks = [TaskWithUser(
        id=i,
        title=f'Task {i}',
        user_id=i % 10
    ) for i in range(1000)]

    def sync_resolve():
        return asyncio.run(Resolver().resolve(tasks))
    benchmark(sync_resolve)
