"""ABAC condition evaluation engine.

Evaluates policy conditions against subject (user) and resource attributes.

Condition format:
{
    "and": [
        {"field": "resource.department_id", "op": "eq", "value": "subject.department_id"},
        {"field": "resource.visibility", "op": "neq", "value": "confidential"}
    ]
}

Supported operators: eq, neq, gt, lt, gte, lte, in
Field references: "subject.xxx" or "resource.xxx"
Values: literal values or "subject.xxx" / "resource.xxx" references
"""

from __future__ import annotations


def evaluate_conditions(conditions: dict | None, subject: dict, resource: dict) -> bool:
    """Evaluate ABAC conditions against subject and resource attributes.

    Args:
        conditions: Condition dict with "and"/"or" logic, or None (always True).
        subject: User attributes dict (e.g. {"department_id": 1, "level": 3}).
        resource: Resource attributes dict (e.g. {"department_id": 1, "visibility": "public"}).

    Returns:
        True if conditions are satisfied (or conditions is None/empty).
    """
    if conditions is None:
        return True

    if not conditions:
        return True

    return _evaluate_node(conditions, subject, resource)


def _evaluate_node(node: dict, subject: dict, resource: dict) -> bool:
    """Recursively evaluate a condition node."""
    if "and" in node:
        return all(_evaluate_node(child, subject, resource) for child in node["and"])
    if "or" in node:
        return any(_evaluate_node(child, subject, resource) for child in node["or"])

    # Leaf condition: {"field": ..., "op": ..., "value": ...}
    return _evaluate_leaf(node, subject, resource)


def _evaluate_leaf(leaf: dict, subject: dict, resource: dict) -> bool:
    """Evaluate a single condition leaf."""
    field_ref = leaf["field"]
    op = leaf["op"]
    raw_value = leaf["value"]

    # Resolve the left-hand side (field reference)
    actual = _resolve_ref(field_ref, subject, resource)

    # Resolve the right-hand side (value, which may also be a reference)
    expected = _resolve_value(raw_value, subject, resource)

    return _compare(actual, op, expected)


def _resolve_ref(ref: str, subject: dict, resource: dict):
    """Resolve a field reference like 'resource.department_id' or 'subject.level'."""
    parts = ref.split(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid field reference: {ref}")

    scope, attr = parts
    if scope == "subject":
        return subject.get(attr)
    elif scope == "resource":
        return resource.get(attr)
    else:
        raise ValueError(f"Unknown scope in field reference: {scope}")


def _resolve_value(value, subject: dict, resource: dict):
    """Resolve a value that may be a literal or a reference string."""
    if isinstance(value, str) and ("." in value) and (value.startswith("subject.") or value.startswith("resource.")):
        return _resolve_ref(value, subject, resource)
    return value


def _compare(actual, op: str, expected) -> bool:
    """Compare actual vs expected using the given operator."""
    if actual is None:
        return False

    if op == "eq":
        return actual == expected
    elif op == "neq":
        return actual != expected
    elif op == "gt":
        return actual > expected
    elif op == "lt":
        return actual < expected
    elif op == "gte":
        return actual >= expected
    elif op == "lte":
        return actual <= expected
    elif op == "in":
        if isinstance(expected, list):
            return actual in expected
        return actual in expected
    else:
        raise ValueError(f"Unknown operator: {op}")
