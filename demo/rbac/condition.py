"""Named ABAC condition definitions.

Each condition maps a name to:
- evaluate(subject_attrs, resource_attrs) -> bool: Python ABAC evaluator
- build_scope(subject_attrs) -> (ids, apply): Build scope tree fragment

Conditions are NOT stored in the database — only the condition name is stored.
The actual filter logic is defined here in Python code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any


@dataclass
class ConditionDef:
    evaluate: Callable[[dict, dict], bool]
    build_scope: Callable[[dict], tuple[list[int] | None, Callable[[Any], Any] | None]]


REGISTRY: dict[str, ConditionDef] = {}


def register(name, evaluate, build_scope):
    REGISTRY[name] = ConditionDef(evaluate=evaluate, build_scope=build_scope)


def get_condition(name: str) -> ConditionDef | None:
    return REGISTRY.get(name)


def evaluate_condition(name: str | None, subject: dict, resource: dict) -> bool:
    """Evaluate named condition. None -> True (unconditional)."""
    if name is None:
        return True
    cond = REGISTRY.get(name)
    if cond is None:
        return True
    return cond.evaluate(subject, resource)


# ── Condition definitions ──


def _same_dept_build_scope(subj):
    return (subj.get('department_ids', []), None)


register(
    'same_dept',
    evaluate=lambda subj, res: res.get('department_id') in subj.get('department_ids', []),
    build_scope=_same_dept_build_scope,
)


def _same_dept_non_confidential_build_scope(subj):
    from .models import Department

    apply = lambda stmt: stmt.where(Department.visibility != 'confidential')
    return (subj.get('department_ids', []), apply)


register(
    'same_dept_non_confidential',
    evaluate=lambda subj, res: (
        res.get('department_id') in subj.get('department_ids', [])
        and res.get('visibility') != 'confidential'
    ),
    build_scope=_same_dept_non_confidential_build_scope,
)


def _public_internal_build_scope(subj):
    from .models import Department

    apply = lambda stmt: stmt.where(Department.visibility.in_(['public', 'internal']))
    return (None, apply)


register(
    'public_internal_only',
    evaluate=lambda subj, res: res.get('visibility') in ['public', 'internal'],
    build_scope=_public_internal_build_scope,
)
