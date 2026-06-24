"""Detect naming-convention trap: `post_default_handler` + `default_handler` field.

`post_default_handler` is a reserved finalizer (runs after all named `post_*`,
no field auto-binding). The `post_<field>` convention elsewhere implies that
`post_default_handler` would populate a field named `default_handler`. When a
class declares both, the method's return value is silently discarded while
the field sits at its default — a confusing, debug-resistant state.

The framework must raise at metadata-build time so the user picks a clear
path: rename the method or drop the field.
"""

import pytest
from pydantic import BaseModel

from pydantic_resolve import Resolver


# ──────────────────────────────────────────────────────────
# Test 1: conflict raises ValueError
# ──────────────────────────────────────────────────────────

class WithConflict(BaseModel):
    default_handler: str = ""
    other: int = 0

    def post_default_handler(self):
        # User likely expects this return value to populate `default_handler`.
        # It will NOT — post_default_handler is a finalizer with no auto-binding.
        return "computed"


@pytest.mark.asyncio
async def test_conflict_between_post_default_handler_and_field_raises():
    """Declaring both post_default_handler method and default_handler field must raise."""
    with pytest.raises(ValueError, match="post_default_handler"):
        await Resolver().resolve(WithConflict())


# ──────────────────────────────────────────────────────────
# Test 2: method only — no conflict, normal finalizer behavior
# ──────────────────────────────────────────────────────────

class MethodOnly(BaseModel):
    value: int = 0
    summary: str = ""

    def post_default_handler(self):
        self.summary = f"value is {self.value}"


@pytest.mark.asyncio
async def test_method_only_works():
    """post_default_handler without a same-named field is the normal finalizer path."""
    result = await Resolver().resolve(MethodOnly(value=42))
    assert result.summary == "value is 42"


# ──────────────────────────────────────────────────────────
# Test 3: field only — no conflict, field is just a plain field
# ──────────────────────────────────────────────────────────

class FieldOnly(BaseModel):
    default_handler: str = "plain"


@pytest.mark.asyncio
async def test_field_only_works():
    """A `default_handler` field without the method is just a normal field."""
    result = await Resolver().resolve(FieldOnly())
    assert result.default_handler == "plain"


# ──────────────────────────────────────────────────────────
# Test 4: method + unrelated field — no conflict
# ──────────────────────────────────────────────────────────

class MethodWithUnrelatedField(BaseModel):
    finalize_result: str = ""

    def post_default_handler(self):
        self.finalize_result = "done"


@pytest.mark.asyncio
async def test_method_with_unrelated_field_works():
    """post_default_handler can set any other field by mutating self."""
    result = await Resolver().resolve(MethodWithUnrelatedField())
    assert result.finalize_result == "done"
