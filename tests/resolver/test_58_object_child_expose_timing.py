"""Verify object_field children see ancestor context from AFTER resolve completes.

Issue: In BFS _traverse Phase A, object_children's ancestor context is built
BEFORE resolve methods execute. If a node exposes a field whose value is
produced by a resolve_ method, object_field children see stale (pre-resolve)
values while resolve-returned children see correct (post-resolve) values.

This test constructs that exact scenario:
- Root exposes 'target' via __pydantic_resolve_expose__
- Root has resolve_target that sets the exposed field
- Root also has an object_field child (no resolve method)
- Both children (resolve-returned and object_field) read ancestor_context['target']
- Both should see the SAME resolved value
"""

import pytest
from pydantic import BaseModel
from typing import Optional
from pydantic_resolve.resolver import Resolver


# ──────────────────────────────────────────────────────────
# Scenario: resolve sets the exposed field, object_field child reads it
# ──────────────────────────────────────────────────────────

class ObjectChild(BaseModel):
    """Child reached via object_field (no resolve_ method on parent's field)."""
    name: str
    target_from_ancestor: str = ""

    def resolve_target_from_ancestor(self, ancestor_context):
        return ancestor_context.get("target", "MISSING")


class ResolveChild(BaseModel):
    """Child reached via resolve_ method return value."""
    name: str
    target_from_ancestor: str = ""

    def resolve_target_from_ancestor(self, ancestor_context):
        return ancestor_context.get("target", "MISSING")


class Root(BaseModel):
    __pydantic_resolve_expose__ = {"target": "target"}

    target: str = "INITIAL"
    # object_field child (no resolve method, traversed directly)
    obj_child: Optional[ObjectChild] = None
    # resolve-returned children
    resolved_children: list[ResolveChild] = []

    def resolve_target(self):
        return "RESOLVED"

    def resolve_resolved_children(self):
        return [dict(name="from_resolve")]


@pytest.mark.asyncio
async def test_object_child_sees_resolved_expose_value():
    """Object_field child must see the same ancestor context as resolve-returned children."""
    root = Root(obj_child=ObjectChild(name="from_object_field"))
    result = await Resolver().resolve(root)

    # resolve_target should have set target to "RESOLVED"
    assert result.target == "RESOLVED"

    # resolve-returned child should see "RESOLVED" (this always worked)
    assert result.resolved_children[0].target_from_ancestor == "RESOLVED"

    # object_field child should ALSO see "RESOLVED" (this is the bug)
    assert result.obj_child.target_from_ancestor == "RESOLVED", (
        f"object_field child saw '{result.obj_child.target_from_ancestor}' "
        f"instead of 'RESOLVED' — ancestor context was built before resolve ran"
    )


# ──────────────────────────────────────────────────────────
# Variant: multiple levels of object_field nesting
# ──────────────────────────────────────────────────────────

class GrandChild(BaseModel):
    value: str = ""

    def resolve_value(self, ancestor_context):
        return ancestor_context.get("target", "MISSING")


class MiddleNode(BaseModel):
    grand_child: GrandChild = None


class RootWithNestedObject(BaseModel):
    __pydantic_resolve_expose__ = {"target": "target"}

    target: str = "INITIAL"
    middle: Optional[MiddleNode] = None

    def resolve_target(self):
        return "RESOLVED"


@pytest.mark.asyncio
async def test_nested_object_child_sees_resolved_expose_value():
    """Nested object_field children must also see resolved ancestor context."""
    root = RootWithNestedObject(
        middle=MiddleNode(grand_child=GrandChild())
    )
    result = await Resolver().resolve(root)

    assert result.target == "RESOLVED"
    assert result.middle.grand_child.value == "RESOLVED", (
        f"nested object_field child saw '{result.middle.grand_child.value}' "
        f"instead of 'RESOLVED'"
    )
