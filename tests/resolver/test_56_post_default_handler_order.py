"""Verify post_default_handler runs AFTER all named post_* methods.

post_default_handler is the catch-all post-processing hook. It must
execute strictly after all named post_* methods on the same node,
so it can observe fields set by those methods.
"""

from pydantic import BaseModel
from pydantic_resolve import Resolver

import pytest


# ──────────────────────────────────────────────────────────
# Test 1: post_default_handler sees fields set by named post_*
# ──────────────────────────────────────────────────────────

class Leaf(BaseModel):
    value: int = 0
    doubled: int = 0

    def post_doubled(self):
        return self.value * 2


class Branch(BaseModel):
    leaves: list[Leaf] = []
    leaf_count: int = 0
    doubled_sum: int = 0
    summary: str = ""

    def post_leaf_count(self):
        return len(self.leaves)

    def post_doubled_sum(self):
        return sum(leaf.doubled for leaf in self.leaves)

    def post_default_handler(self):
        # This must see the results of post_leaf_count and post_doubled_sum
        self.summary = f"{self.leaf_count} leaves, doubled_sum={self.doubled_sum}"


@pytest.mark.asyncio
async def test_post_default_handler_runs_after_named_posts():
    """post_default_handler must see fields set by named post_* methods."""
    branch = Branch(leaves=[Leaf(value=1), Leaf(value=2), Leaf(value=3)])
    result = await Resolver().resolve(branch)

    # Named post_* results
    assert result.leaf_count == 3
    assert result.doubled_sum == 12  # (1*2 + 2*2 + 3*2)

    # post_default_handler should see those results
    assert result.summary == "3 leaves, doubled_sum=12"


# ──────────────────────────────────────────────────────────
# Test 2: post_default_handler sees nested resolution results
# ──────────────────────────────────────────────────────────

class Child(BaseModel):
    name: str
    score: int = 0

    def post_score(self):
        return len(self.name) * 10


class Parent(BaseModel):
    children: list[Child] = []
    total_score: int = 0
    report: str = ""

    def post_total_score(self):
        return sum(c.score for c in self.children)

    def post_default_handler(self):
        self.report = f"Total: {self.total_score}"


@pytest.mark.asyncio
async def test_post_default_handler_sees_nested_post_results():
    """post_default_handler must see results from post methods on children."""
    parent = Parent(children=[
        Child(name="Alice"),
        Child(name="Bob"),
    ])
    result = await Resolver().resolve(parent)

    assert result.total_score == 80  # 50 + 30
    assert result.report == "Total: 80"


# ──────────────────────────────────────────────────────────
# Test 3: post_default_handler on multiple nodes at same level
# ──────────────────────────────────────────────────────────

class Item(BaseModel):
    a: int
    b: int
    a_plus_b: int = 0
    description: str = ""

    def post_a_plus_b(self):
        return self.a + self.b

    def post_default_handler(self):
        self.description = f"sum={self.a_plus_b}"


@pytest.mark.asyncio
async def test_post_default_handler_on_multiple_sibling_nodes():
    """Each node's post_default_handler must see its own post_* results."""
    items = [
        Item(a=1, b=2),
        Item(a=10, b=20),
        Item(a=100, b=200),
    ]
    results = await Resolver().resolve(items)

    assert results[0].description == "sum=3"
    assert results[1].description == "sum=30"
    assert results[2].description == "sum=300"


# ──────────────────────────────────────────────────────────
# Test 4: post_default_handler with context parameter
# ──────────────────────────────────────────────────────────

class Service(BaseModel):
    items: list[str] = []
    item_count: int = 0
    greeting: str = ""

    def post_item_count(self):
        return len(self.items)

    def post_default_handler(self, context):
        self.greeting = f"{context['prefix']}: {self.item_count} items"


@pytest.mark.asyncio
async def test_post_default_handler_with_context_after_named_posts():
    """post_default_handler with context param still runs after named posts."""
    svc = Service(items=["a", "b", "c"])
    result = await Resolver(context={"prefix": "Hello"}).resolve(svc)

    assert result.item_count == 3
    assert result.greeting == "Hello: 3 items"
