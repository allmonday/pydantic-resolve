import asyncio
from typing import List
from pydantic import BaseModel

from pydantic_resolve import Resolver

# ============================================================================
# Test Data Classes
# ============================================================================

class RelatedProduct(BaseModel):
    id: int
    name: str
    category: str
    price: float = 0.0

class Product(BaseModel):
    id: int
    name: str
    category: str
    price: float = 0.0

    related_products: List[RelatedProduct] = []
    async def resolve_related_products(self) -> List[RelatedProduct]:
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
    id: int
    value: int

    calculated: int = 0
    def post_calculated(self):
        return self.value * 2

# ============================================================================
# Benchmarks
# ============================================================================

def test_large_dataset_basic(benchmark):
    products = [
        Product(
            id=i,
            name=f'Product {i}',
            category=f'Cat {i % 10}',
            price=float(i * 10)
        )
        for i in range(1000)
    ]

    def sync_resolve():
        return asyncio.run(Resolver().resolve(products))
    benchmark(sync_resolve)

def test_large_dataset_with_post(benchmark):
    items = [LargeItem(id=i, value=i) for i in range(2000)]

    def sync_resolve():
        return asyncio.run(Resolver().resolve(items))
    benchmark(sync_resolve)

def test_very_large_dataset(benchmark):
    items = [LargeItem(id=i, value=i) for i in range(5000)]

    def sync_resolve():
        return asyncio.run(Resolver().resolve(items))
    benchmark(sync_resolve)

def test_large_dataset_list_input(benchmark):
    products = [
        Product(
            id=i,
            name=f'Product {i}',
            category=f'Cat {i % 10}',
            price=float(i * 10)
        )
        for i in range(1000)
    ]

    def sync_resolve():
        return asyncio.run(Resolver().resolve(products))
    benchmark(sync_resolve)


def test_large_dataset_simple_objects(benchmark):
    class SimpleProduct(BaseModel):
        id: int
        name: str
        price: float

    products = [
        SimpleProduct(id=i, name=f'Product {i}', price=float(i))
        for i in range(10000)
    ]

    def sync_resolve():
        return asyncio.run(Resolver().resolve(products))
    benchmark(sync_resolve)
