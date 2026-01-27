import asyncio
from typing import List
from pydantic import BaseModel

from pydantic_resolve import Resolver

# ============================================================================
# Test Data Classes
# ============================================================================

class Node(BaseModel):
    id: int
    level: int

    children: List['Node'] = []
    async def resolve_children(self, context) -> List['Node']:
        if self.level >= context['max_depth']:  # 最大深度
            return []

        remaining = context['remaining']
        if remaining[0] <= 0:
            return []

        branch = min(context['branch'], remaining[0])
        remaining[0] -= branch

        await asyncio.sleep(0.0001)
        return [
            Node(
                id=i,
                level=self.level + 1
            )
            for i in range(branch)
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

def test_deep_nesting_standard(benchmark):
    root = Node(id=0, level=0)
    context = {'remaining': [363], 'max_depth': 5, 'branch': 3}

    def sync_resolve():
        context['remaining'][0] = 363
        return asyncio.run(Resolver(context=context).resolve(root))
    benchmark(sync_resolve)

def test_deep_nesting_wide(benchmark):
    class WideNode(BaseModel):
        id: int
        level: int

        children: List['WideNode'] = []
        async def resolve_children(self, context) -> List['WideNode']:
            if self.level >= context['max_depth']:
                return []

            remaining = context['remaining']
            if remaining[0] <= 0:
                return []

            branch = min(context['branch'], remaining[0])
            remaining[0] -= branch

            await asyncio.sleep(0.0001)
            return [
                WideNode(id=i, level=self.level + 1)
                for i in range(branch)
            ]

        descendant_count: int = 0
        def post_descendant_count(self):
            return 1 + sum(child.descendant_count for child in self.children)

    WideNode.model_rebuild()

    root = WideNode(id=0, level=0)
    context = {'remaining': [363], 'max_depth': 3, 'branch': 10}

    def sync_resolve():
        context['remaining'][0] = 363
        return asyncio.run(Resolver(context=context).resolve(root))
    benchmark(sync_resolve)

def test_deep_nesting_narrow(benchmark):
    class NarrowNode(BaseModel):
        id: int
        level: int

        children: List['NarrowNode'] = []
        async def resolve_children(self, context) -> List['NarrowNode']:
            if self.level >= context['max_depth']:
                return []

            remaining = context['remaining']
            if remaining[0] <= 0:
                return []

            branch = min(context['branch'], remaining[0])
            remaining[0] -= branch

            await asyncio.sleep(0.0001)
            return [
                NarrowNode(id=i, level=self.level + 1)
                for i in range(branch)
            ]

        descendant_count: int = 0
        def post_descendant_count(self):
            return 1 + sum(child.descendant_count for child in self.children)

    NarrowNode.model_rebuild()

    root = NarrowNode(id=0, level=0)
    context = {'remaining': [363], 'max_depth': 8, 'branch': 2}

    def sync_resolve():
        context['remaining'][0] = 363
        return asyncio.run(Resolver(context=context).resolve(root))
    benchmark(sync_resolve)

def test_deep_nesting_with_post_calculations(benchmark):
    root = Node(id=0, level=0)
    context = {'remaining': [363], 'max_depth': 5, 'branch': 3}

    def sync_resolve():
        context['remaining'][0] = 363
        return asyncio.run(Resolver(context=context).resolve(root))
    benchmark(sync_resolve)

def test_deep_nesting_multiple_roots(benchmark):
    class ShallowNode(BaseModel):
        id: int
        level: int

        children: List['ShallowNode'] = []
        async def resolve_children(self, context) -> List['ShallowNode']:
            if self.level >= context['max_depth']:
                return []

            remaining = context['remaining']
            if remaining[0] <= 0:
                return []

            branch = min(context['branch'], remaining[0])
            remaining[0] -= branch

            await asyncio.sleep(0.0001)
            return [
                ShallowNode(
                    id=i,
                    level=self.level + 1
                )
                for i in range(branch)
            ]

        descendant_count: int = 0
        def post_descendant_count(self):
            return 1 + sum(child.descendant_count for child in self.children)

    ShallowNode.model_rebuild()

    roots = [ShallowNode(id=i, level=0) for i in range(10)]
    context = {'remaining': [363], 'max_depth': 3, 'branch': 3}

    def sync_resolve():
        context['remaining'][0] = 363
        return asyncio.run(Resolver(context=context).resolve(roots))
    benchmark(sync_resolve)
