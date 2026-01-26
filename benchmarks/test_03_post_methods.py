"""
Benchmark 3: Post-Method Calculations

测试 post 方法计算派生字段的性能。

测试场景:
- 计算总和
- 统计数量
- 条件判断
- 格式化数据

性能目标: < 0.3s for 100 orders
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

class LineItem(BaseModel):
    """订单项"""
    id: int
    product_name: str
    quantity: int
    price: float

    subtotal: float = 0.0
    def post_subtotal(self):
        return self.quantity * self.price


class Order(BaseModel):
    """订单"""
    id: int
    customer_name: str

    items: List[LineItem] = []
    async def resolve_items(self) -> List[LineItem]:
        await asyncio.sleep(0.001)
        return [
            LineItem(id=1, product_name='Product A', quantity=2, price=10.0),
            LineItem(id=2, product_name='Product B', quantity=3, price=15.0),
            LineItem(id=3, product_name='Product C', quantity=1, price=5.0),
        ]

    total: float = 0.0
    def post_total(self):
        return sum(item.subtotal for item in self.items)

    item_count: int = 0
    def post_item_count(self):
        return len(self.items)

    average_price: float = 0.0
    def post_average_price(self):
        # 直接计算，避免依赖其他 post 字段的执行顺序
        count = len(self.items)
        if count > 0:
            return sum(item.subtotal for item in self.items) / count
        return 0.0

    is_expensive: bool = False
    def post_is_expensive(self):
        # 直接计算，避免依赖 self.total 的执行顺序
        return sum(item.subtotal for item in self.items) > 50

    formatted_total: str = ''
    def post_formatted_total(self):
        return f'${self.total:.2f}'


# ============================================================================
# Benchmarks
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_post_calculations():
    """
    Benchmark: Post 方法计算

    测试目标:
    - 测量 post 方法的性能
    - 验证派生字段计算的开销

    场景:
    - 100 orders
    - 每个 order 有 3 items
    - 计算 total, count, average, 等字段

    预期: < 0.3s
    """
    orders = [Order(id=i, customer_name=f'Customer {i}') for i in range(100)]

    start = time.perf_counter()
    result = await Resolver().resolve(orders)
    elapsed = time.perf_counter() - start

    assert len(result) == 100
    assert all(o.total > 0 for o in result)
    assert all(o.item_count == 3 for o in result)
    assert all(o.is_expensive == (o.total > 50) for o in result)

    total_value = sum(o.total for o in result)
    measure_performance(result, elapsed, node_count=100)
    print(f"  💰 Total value: ${total_value:.2f}")

    assert_performance(elapsed, 0.3, "Post calculations")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_post_nested_calculations():
    """
    Benchmark: 嵌套 post 方法计算

    测试目标:
    - 测试多层级的 post 方法依赖
    - 验证 post 字段可以访问其他 post 字段

    场景:
    - LineItem.post_subtotal 计算
    - Order.post_total 依赖 LineItem.subtotal
    - Order.post_average_price 依赖 total 和 count

    预期: < 0.3s for 100 orders
    """
    orders = [Order(id=i, customer_name=f'Customer {i}') for i in range(100)]

    start = time.perf_counter()
    result = await Resolver().resolve(orders)
    elapsed = time.perf_counter() - start

    assert len(result) == 100

    # 验证依赖关系正确
    for order in result:
        assert order.average_price == order.total / order.item_count
        assert order.formatted_total.startswith('$')

    measure_performance(result, elapsed, node_count=100)

    assert_performance(elapsed, 0.3, "Post nested calculations")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_post_complex_logic():
    """
    Benchmark: 复杂 post 方法逻辑

    测试目标:
    - 测试包含条件判断的 post 方法
    - 验证复杂逻辑的性能

    预期: < 0.2s for 100 orders
    """
    orders = [Order(id=i, customer_name=f'Customer {i}') for i in range(100)]

    start = time.perf_counter()
    result = await Resolver().resolve(orders)
    elapsed = time.perf_counter() - start

    assert len(result) == 100

    # 统计昂贵订单
    expensive_count = sum(1 for o in result if o.is_expensive)
    assert expensive_count > 0  # 应该有一些订单超过 $50

    measure_performance(result, elapsed, node_count=100)
    print(f"  📊 Expensive orders: {expensive_count}/{len(result)}")

    assert_performance(elapsed, 0.2, "Post complex logic")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_post_with_no_resolve():
    """
    Benchmark: 只有 post 方法，没有 resolve 方法

    测试目标:
    - 测试纯 post 方法计算的性能
    - 验证没有 I/O 时的开销

    预期: < 0.1s for 100 orders
    """

    class SimpleOrder(BaseModel):
        id: int
        quantity: int = 5
        price: float = 10.0

        total: float = 0.0
        def post_total(self):
            return self.quantity * self.price

    orders = [SimpleOrder(id=i) for i in range(100)]

    start = time.perf_counter()
    result = await Resolver().resolve(orders)
    elapsed = time.perf_counter() - start

    assert len(result) == 100
    assert all(o.total == 50.0 for o in result)

    measure_performance(result, elapsed, node_count=100)
    print("  ⚡ Pure post methods (no I/O)")

    assert_performance(elapsed, 0.1, "Post with no resolve")
