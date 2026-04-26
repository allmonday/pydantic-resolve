"""RBAC/ABAC Demo: Multi-level permission queries with DataLoader batching.

Demonstrates pydantic-resolve + SQLAlchemy with three resource tables
(departments, projects, documents) and FK-based ancestor tracing
instead of closure tables.

Run: uv run python -m demo.rbac.demo
"""

from __future__ import annotations

import asyncio
import json

from pydantic_resolve import Resolver

from .database import cleanup_db, init_db
from .loaders import query_counts, reset_counts
from .schemas import (
    AccessCheckRequest,
    DepartmentNode,
    DocumentListView,
    UserPermissionView,
    UserPermissionWithGroupsView,
    UserScopeView,
)


def _print_header(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _print_result(obj, label: str = ""):
    if label:
        print(f"\n{label}:")
    if hasattr(obj, "model_dump"):
        data = obj.model_dump()
    elif isinstance(obj, list):
        data = [item.model_dump() if hasattr(item, "model_dump") else item for item in obj]
    else:
        data = obj
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def _print_query_counts():
    print(f"\n  SQL queries executed: {json.dumps(dict(query_counts), indent=4)}")


async def run():
    await init_db()

    try:
        await _scenario_1_user_permission_expansion()
        await _scenario_2_abac_condition_evaluation()
        await _scenario_3_resource_hierarchy()
        await _scenario_4_batch_permission_check()
        await _scenario_5_mail_group_permissions()
        await _scenario_6_scope_pre_constraint()
    finally:
        await cleanup_db()


async def _scenario_1_user_permission_expansion():
    """Scenario 1: Expand all permissions for a user (dashboard view).

    User -> Roles -> Permissions
    DataLoader ensures batch SQL queries regardless of data volume.
    """
    _print_header("Scenario 1: User Permission Expansion (Dashboard)")
    reset_counts()

    users = [
        UserPermissionView(id=1, name="Alice", email="alice@example.com", level=3),
        UserPermissionView(id=2, name="Bob", email="bob@example.com", level=2),
        UserPermissionView(id=3, name="Charlie", email="charlie@example.com", level=2),
        UserPermissionView(id=4, name="Diana", email="diana@example.com", level=1),
    ]
    results = await Resolver().resolve(users)
    for r in results:
        _print_result(r, f"{r.name}'s full permissions")

    print(f"\n  4 users' permissions expanded with {sum(query_counts.values())} SQL queries:")
    _print_query_counts()
    print("\n  Key insight: DataLoader batches all 4 users into single loader calls")


async def _scenario_2_abac_condition_evaluation():
    """Scenario 2: ABAC condition evaluation — SQL coarse filter + Python fine filter."""
    _print_header("Scenario 2: ABAC Condition Evaluation")
    reset_counts()

    # New IDs:
    # document: 1=Design Doc(dept1,internal), 2=API Doc(dept1,public),
    #           3=Campaign Brief(dept2,internal), 4=Budget Plan(dept2,confidential)
    # project:  1=Project Alpha(dept1,internal), 2=Project Beta(dept1,confidential),
    #           3=Campaign X(dept2,internal)
    test_cases = [
        # (user_id, user_depts, user_level, res_type, res_id, action, expected, description)
        (2, [1], 2, "document", 1, "read", True, "Bob reads Design Doc (same dept, internal)"),
        (2, [1], 2, "document", 1, "write", True, "Bob writes Design Doc (same dept, internal)"),
        (2, [1], 2, "project", 2, "write", True, "Bob writes Project Beta (confidential, admin via eng-leads group)"),
        (3, [2], 2, "document", 3, "read", True, "Charlie reads Campaign Brief (same dept)"),
        (3, [2], 2, "document", 1, "write", False, "Charlie writes Design Doc (different dept)"),
        (4, [2], 1, "document", 2, "read", True, "Diana reads API Doc (public, viewer can read)"),
        (4, [2], 1, "document", 4, "read", False, "Diana reads Budget Plan (confidential, viewer blocked)"),
        (4, [2], 1, "document", 1, "read", True, "Diana reads Design Doc (internal, viewer can read)"),
        (4, [2], 1, "document", 1, "write", False, "Diana writes Design Doc (viewer has no write permission)"),
        (1, [1, 2], 3, "document", 3, "read", True, "Alice reads Campaign Brief (cross-dept admin)"),
        (1, [1, 2], 3, "document", 4, "write", True, "Alice writes Budget Plan (cross-dept admin)"),
        # Permission.resource_type scoping: export_doc only applies to documents
        (4, [2], 1, "document", 2, "export", True, "Diana exports API Doc (export_doc applies to documents)"),
        (4, [2], 1, "project", 1, "export", False, "Diana exports Project Alpha (export_doc does NOT apply to projects)"),
    ]

    print("\n  Testing ABAC condition evaluation:")
    print(f"  {'Test':<60} {'Expected':>8} {'Actual':>8} {'Result':>8}")
    print(f"  {'-' * 60} {'-' * 8} {'-' * 8} {'-' * 8}")

    for user_id, depts, level, res_type, res_id, action, expected, desc in test_cases:
        reset_counts()
        req = AccessCheckRequest(
            user_id=user_id,
            user_depts=depts,
            user_level=level,
            action=action,
            target_resources=[(res_type, res_id)],
        )
        result = await Resolver().resolve(req)

        if result.resources:
            actual = result.resources[0].accessible
            status = "PASS" if actual == expected else "FAIL"
            reason = result.resources[0].access_reason[:40]
            print(f"  {desc:<60} {str(expected):>8} {str(actual):>8} {status:>8}")
            if actual != expected:
                print(f"    Reason: {reason}")

    _print_query_counts()
    print("\n  Key insight: ABAC conditions are split into two stages:")
    print("  1. SQL coarse filter: ancestor tracing + match action (candidate_permissions_loader)")
    print("  2. Python fine filter: evaluate conditions in post_accessible()")


async def _scenario_3_resource_hierarchy():
    """Scenario 3: Resource tree traversal — Dept → Project → Document.

    Uses DataLoader to batch-load children at each level.
    """
    _print_header("Scenario 3: Resource Hierarchy (Dept → Project → Document)")
    reset_counts()

    # Load both departments as tree roots
    eng = DepartmentNode(id=1, name="Engineering", owner_id=1, visibility="internal")
    mkt = DepartmentNode(id=2, name="Marketing", owner_id=3, visibility="internal")

    eng_result = await Resolver().resolve(eng)
    mkt_result = await Resolver().resolve(mkt)

    _print_result(eng_result, "Engineering tree")
    _print_result(mkt_result, "Marketing tree")

    _print_query_counts()
    total = sum(query_counts.values())
    print(f"\n  Key insight: 2 departments expanded with {total} SQL queries")
    print("  department_projects_loader: 1 query for all depts")
    print("  project_documents_loader: 1 query for all projects")


async def _scenario_4_batch_permission_check():
    """Scenario 4: Batch permission check on multiple documents."""
    _print_header("Scenario 4: Batch Permission Check (List View)")

    # Check all documents for Bob (department 1, level 2)
    reset_counts()
    view = DocumentListView(user_id=2, user_depts=[1], user_level=2)
    result = await Resolver().resolve(view)

    print("\n  Bob's access to all documents:")
    print(f"  {'Document':<20} {'Dept':>6} {'Visibility':<14} {'Read':>6} {'Write':>6} {'Reason'}")
    print(f"  {'-' * 20} {'-' * 6} {'-' * 14} {'-' * 6} {'-' * 6} {'-' * 20}")

    for doc in result.documents:
        print(
            f"  {doc.name:<20} {str(doc.department_id):>6} {doc.visibility:<14} "
            f"{str(doc.can_read):>6} {str(doc.can_write):>6} {doc.access_reason}"
        )

    _print_query_counts()
    doc_count = len(result.documents)
    print(f"\n  Key insight: {doc_count} documents checked with {sum(query_counts.values())} SQL queries")
    print("  DataLoader batches all permission checks into a single candidate_permissions_loader call")


async def _scenario_5_mail_group_permissions():
    """Scenario 5: Mail group-based permission inheritance."""
    _print_header("Scenario 5: Mail Group Permission Inheritance")
    reset_counts()

    # Show Bob's mail groups and roles
    bob = UserPermissionWithGroupsView(
        id=2, name="Bob", email="bob@example.com", level=2
    )
    result = await Resolver().resolve(bob)
    _print_result(result, "Bob's profile: direct roles + mail groups")

    _print_query_counts()
    print("\n  Bob's permission sources:")
    print("  - Direct: manager role (from user_roles)")
    print("  - Group:  manager via engineering-all, admin via eng-leads")
    print("  (eng-leads gives Bob admin access he wouldn't have directly)")

    # Show how group-inherited admin permission affects access checks
    reset_counts()
    print("\n  Access checks with group-inherited permissions:")

    test_cases = [
        # Bob normally can't write confidential, but eng-leads → admin → can do anything
        (2, [1], 2, "project", 2, "write", True,
         "Bob writes Project Beta (confidential, admin via eng-leads)"),
        # Bob can now delete documents too (admin privilege from group)
        (2, [1], 2, "document", 1, "delete", True,
         "Bob deletes Design Doc (admin via eng-leads)"),
    ]

    print(f"  {'Test':<60} {'Expected':>8} {'Actual':>8} {'Result':>8}")
    print(f"  {'-' * 60} {'-' * 8} {'-' * 8} {'-' * 8}")

    for user_id, depts, level, res_type, res_id, action, expected, desc in test_cases:
        reset_counts()
        req = AccessCheckRequest(
            user_id=user_id,
            user_depts=depts,
            user_level=level,
            action=action,
            target_resources=[(res_type, res_id)],
        )
        check_result = await Resolver().resolve(req)

        if check_result.resources:
            actual = check_result.resources[0].accessible
            status = "PASS" if actual == expected else "FAIL"
            reason = check_result.resources[0].access_reason[:50]
            matched = check_result.resources[0].matched_rule
            print(f"  {desc:<60} {str(expected):>8} {str(actual):>8} {status:>8}")
            print(f"    Matched: {matched} | Reason: {reason}")
            if actual != expected:
                perms = check_result.resources[0].candidate_perms
                print(f"    Candidate perms: {[p.permission_name for p in perms]}")

    _print_query_counts()
    print("\n  Key insight: Group-inherited permissions merge seamlessly")
    print("  with direct permissions in candidate_permissions_loader.")
    print("  The ABAC fine filter (post_*) evaluates all sources uniformly.")


async def _scenario_6_scope_pre_constraint():
    """Scenario 6: Scope pre-constraint with ER Diagram + AutoLoad.

    All levels (User → Departments → Projects → Documents) use AutoLoad + scope.
    User is an entity, departments loaded via scope-aware loader.
    Compare with Scenario 3 which loads ALL data then filters via post_*.
    """
    _print_header("Scenario 6: Scope Pre-Constraint (ER Diagram + AutoLoad)")

    from .scope import compute_scope_tree, inject_access_scope

    # ── Demo 1: Eve (restricted_viewer) — resource-scoped permission ──
    print("\n  ── Eve (restricted_viewer, resource-scoped) ──")
    reset_counts()

    eve_scope = await compute_scope_tree(user_id=5, action="read")
    print(f"\n  Scope tree for Eve:")
    print(f"  {json.dumps(eve_scope, indent=4, default=str)}")

    eve = UserScopeView(id=5, name="Eve")
    object.__setattr__(eve, '_access_scope_tree', eve_scope)

    result = await Resolver(
        resolved_hooks=[inject_access_scope],
        enable_from_attribute_in_type_adapter=True,
    ).resolve(eve)

    _print_result(result, "Eve's accessible resources")

    _print_query_counts()
    print("\n  Eve can only see Project Alpha (project 1), no department wrapper")

    # ── Demo 2: Alice (admin) — global permission -> is_all=True ──
    print("\n  ── Alice (admin, global permission) ──")
    reset_counts()

    alice_scope = await compute_scope_tree(user_id=1, action="read")
    print(f"\n  Scope tree for Alice: {json.dumps(alice_scope, indent=4, default=str)}")

    alice = UserScopeView(id=1, name="Alice")
    object.__setattr__(alice, '_access_scope_tree', alice_scope)

    result2 = await Resolver(
        resolved_hooks=[inject_access_scope],
        enable_from_attribute_in_type_adapter=True,
    ).resolve(alice)

    _print_result(result2, "Alice's accessible departments")
    _print_query_counts()

    # ── Demo 3: Bob (manager) — global ABAC permission ──
    print("\n  ── Bob (manager, global ABAC permission) ──")
    reset_counts()

    bob_scope = await compute_scope_tree(user_id=2, action="read")
    print(f"\n  Scope tree for Bob: {json.dumps(bob_scope, indent=4, default=str)}")

    bob = UserScopeView(id=2, name="Bob")
    object.__setattr__(bob, '_access_scope_tree', bob_scope)

    result3 = await Resolver(
        resolved_hooks=[inject_access_scope],
        enable_from_attribute_in_type_adapter=True,
    ).resolve(bob)

    _print_result(result3, "Bob's accessible departments")
    _print_query_counts()

    # ── Summary ──
    print("\n  ── Key insight ──")
    print("  All levels use AutoLoad + scope (User as entity, scope-aware loader)")
    print("  - Eve: [ScopeNode(type='projects', ids=[1])] → direct project access, no ancestor tracing")
    print("  - Alice: [ScopeNode(is_all=True)] → all departments, no constraint")
    print("  - Bob: [ScopeNode(is_all=True, filter_fn=...)] → ABAC-constrained access")
    print("  - No permission: [] → empty result")
    print("  Strategy B: only explicitly authorized levels appear in scope tree")
    print("  Scope pre-constraint is essential for pagination + permissions coexistence")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
