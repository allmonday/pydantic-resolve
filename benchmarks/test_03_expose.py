import asyncio
from typing import List
from pydantic import BaseModel

from pydantic_resolve import Resolver

# ============================================================================
# Test Data Classes
# ============================================================================

class GrandChildEx(BaseModel):
    id: int
    name: str

    root_name: str = ''
    def post_root_name(self, ancestor_context):
        name = ancestor_context.get('root_name', '')
        return str(name) if name else ''

    parent_id: str = ''
    def post_parent_id(self, ancestor_context):
        parent_id = ancestor_context.get('parent_path')
        return str(parent_id) if parent_id is not None else ''

class ChildEx(BaseModel):
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

def test_expose_three_levels(benchmark):
    roots = [RootEx(id=i, name=f'Root {i}') for i in range(20)]

    def sync_resolve():
        return asyncio.run(Resolver().resolve(roots))
    benchmark(sync_resolve)