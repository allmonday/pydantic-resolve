"""Tests for ICollector implementations with custom config / state.

Captures the bug scenarios from #293. These tests are EXPECTED TO FAIL on
current master — they exist to scope the bug before we agree on a fix.

The clone mechanism in ``_clone_collector`` currently:
- Bypasses ``__init__`` via ``cls.__new__(cls)``, dropping any instance
  attributes the subclass sets in ``__init__`` (e.g. ``key_fn``, ``n``).
- Hard-codes ``new.val = []``, which is wrong for any collector whose
  ``val`` is not a list (dict, set, custom aggregator, ...).

Run::

    pytest tests/resolver/test_collector_subclass.py -v
"""
import pytest
from pydantic import BaseModel
from typing import List

from pydantic_resolve import ICollector, Collector, Resolver


# =============================================================================
# Scenario 1: MapCollector (implements ICollector, dict-based val)
# =============================================================================
# Real-world need: dedupe descendant values by a key function.
# - val is a dict, not a list.
# - config (key_fn) is set in __init__.
# Currently fails: _clone_collector bypasses __init__ (loses key_fn) and
# overwrites val with [] (breaks the dict assumption).

class MapCollector(ICollector):
    def __init__(self, alias: str, key_fn):
        self.alias = alias
        self.key_fn = key_fn
        self.val: dict = {}

    def add(self, val):
        self.val[self.key_fn(val)] = val

    def values(self):
        return list(self.val.values())


class _Comment(BaseModel):
    __pydantic_resolve_collect__ = {'email': 'unique_emails'}
    email: str


class _Post(BaseModel):
    comments: List[_Comment] = []
    unique_emails: List[str] = []

    def post_unique_emails(self, collector=MapCollector('unique_emails', key_fn=lambda v: v)):
        return collector.values()


@pytest.mark.asyncio
async def test_map_collector_dedupes():
    """MapCollector should dedupe by key_fn — val is dict, config is key_fn."""
    post = _Post(comments=[
        _Comment(email='a@x.com'),
        _Comment(email='a@x.com'),
        _Comment(email='b@x.com'),
    ])
    result = await Resolver().resolve(post)
    assert sorted(result.unique_emails) == ['a@x.com', 'b@x.com']


# =============================================================================
# Scenario 2: Sibling branches must not share collector state
# =============================================================================
# Two Post nodes under one Root. Each Post's post_unique_emails should only
# see its own comments. Today this passes for the built-in Collector (because
# new.val = [] is hard-coded), but with any custom ICollector it will leak
# across siblings unless the clone produces truly independent state.

class _Root(BaseModel):
    posts: List[_Post] = []

    def resolve_posts(self):
        return self.posts


@pytest.mark.asyncio
async def test_sibling_branches_isolated():
    """Sibling Post nodes must not mix their unique_emails."""
    root = _Root(posts=[
        _Post(comments=[_Comment(email='a@x.com'), _Comment(email='b@x.com')]),
        _Post(comments=[_Comment(email='c@x.com'), _Comment(email='c@x.com')]),
    ])
    result = await Resolver().resolve(root)
    assert sorted(result.posts[0].unique_emails) == ['a@x.com', 'b@x.com']
    assert sorted(result.posts[1].unique_emails) == ['c@x.com']


# =============================================================================
# Scenario 3: Sequential resolve() on same Resolver must not leak state
# =============================================================================
# Depends on BOTH the #289 fix (object_level_collect_alias_map_store reset)
# AND a correct clone mechanism.

@pytest.mark.asyncio
async def test_sequential_resolve_no_leak():
    """Resolver reused across two trees must not carry collector state over."""
    resolver = Resolver()
    p1 = await resolver.resolve(_Post(comments=[_Comment(email='a@x.com')]))
    p2 = await resolver.resolve(_Post(comments=[_Comment(email='b@x.com')]))
    assert p1.unique_emails == ['a@x.com']
    assert p2.unique_emails == ['b@x.com']


# =============================================================================
# Scenario 4: Collector subclass that adds config in __init__
# =============================================================================
# Same family of bug as MapCollector, but here the user inherits from Collector
# (the default list-based implementation) and just adds an `n` config attribute.
# Today this fails the same way: n is lost during clone.

class TopNCollector(Collector):
    def __init__(self, alias, n):
        super().__init__(alias)
        self.n = n

    def add(self, val):
        # naive sliding-window top-N by insertion order — good enough to
        # demonstrate that self.n must survive the clone.
        self.val.append(val)
        if len(self.val) > self.n:
            self.val = self.val[-self.n:]


class _Item(BaseModel):
    __pydantic_resolve_collect__ = {'score': 'top_scores'}
    score: int


class _Bucket(BaseModel):
    items: List[_Item] = []
    top_scores: List[int] = []

    def post_top_scores(self, collector=TopNCollector('top_scores', n=2)):
        return collector.values()


@pytest.mark.asyncio
async def test_topn_collector_preserves_n_config():
    """TopNCollector's n must survive clone — currently lost via __new__."""
    bucket = _Bucket(items=[_Item(score=i) for i in [10, 20, 30, 40]])
    result = await Resolver().resolve(bucket)
    assert result.top_scores == [30, 40]


# =============================================================================
# Scenario 5: Backward-compat — existing SubCollector pattern must keep working
# =============================================================================
# This pattern already exists in tests/resolver/test_35_collector.py and must
# NOT regress. SubCollector only overrides add(); no new attrs in __init__.
# Expected: PASS on current master (and after the fix).

class SimpleSubCollector(Collector):
    """Mirrors tests/resolver/test_35_collector.py:8 — no __init__ override."""

    def add(self, val):
        self.val.append(f'sub-{val}')


class _Leaf(BaseModel):
    __pydantic_resolve_collect__ = {'name': 'leaf_names'}
    name: str


class _Branch(BaseModel):
    leaves: List[_Leaf] = []
    decorated: List[str] = []

    def post_decorated(self, collector=SimpleSubCollector('leaf_names')):
        return collector.values()


@pytest.mark.asyncio
async def test_simple_subcollector_still_works():
    """Existing 'only override add()' pattern must keep working post-fix."""
    branch = _Branch(leaves=[_Leaf(name='a'), _Leaf(name='b')])
    result = await Resolver().resolve(branch)
    assert result.decorated == ['sub-a', 'sub-b']
