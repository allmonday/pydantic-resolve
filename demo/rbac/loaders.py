"""DataLoader batch functions for RBAC/ABAC permission queries.

Resources are split into three tables (departments, projects, documents).
Ancestor tracing for permission inheritance uses sequential FK lookups
instead of a closure table, since the hierarchy is only 3 levels deep.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic_resolve.utils.dataloader import build_object

from .database import session_factory

# Global query counter for demonstrating DataLoader batching
query_counts: dict[str, int] = {}


def _count(name: str):
    """Track how many times each loader's batch function is called."""
    query_counts[name] = query_counts.get(name, 0) + 1


def reset_counts():
    """Reset query counters."""
    query_counts.clear()


# ── Basic entity loaders ──


async def user_loader(user_ids: list[int]):
    """Batch load users by ID."""
    _count("user_loader")
    from .models import User
    from sqlalchemy import select

    async with session_factory() as session:
        result = await session.scalars(select(User).where(User.id.in_(user_ids)))
        rows = result.all()
    return list(build_object(rows, user_ids, lambda u: u.id))


async def role_loader(role_ids: list[int]):
    """Batch load roles by ID."""
    _count("role_loader")
    from .models import Role
    from sqlalchemy import select

    async with session_factory() as session:
        result = await session.scalars(select(Role).where(Role.id.in_(role_ids)))
        rows = result.all()
    return list(build_object(rows, role_ids, lambda r: r.id))


# ── Resource loaders ──


async def departments_loader(department_ids: list[int]):
    """Batch load departments by ID."""
    _count("departments_loader")
    from .models import Department
    from sqlalchemy import select

    async with session_factory() as session:
        result = await session.scalars(select(Department).where(Department.id.in_(department_ids)))
        rows = result.all()
    return list(build_object(rows, department_ids, lambda d: d.id))


async def resources_by_keys_loader(keys: list[tuple[str, int]]):
    """Batch load resources by (resource_type, resource_id).

    Returns list[dict | None] — one dict per key, or None if not found.
    """
    _count("resources_by_keys_loader")
    from .models import Department, Document, Project
    from sqlalchemy import select

    dept_ids = [rid for rtype, rid in keys if rtype == "department"]
    proj_ids = [rid for rtype, rid in keys if rtype == "project"]
    doc_ids = [rid for rtype, rid in keys if rtype == "document"]

    obj_map: dict[tuple[str, int], dict] = {}

    async with session_factory() as session:
        if dept_ids:
            rows = (await session.scalars(select(Department).where(Department.id.in_(dept_ids)))).all()
            for r in rows:
                obj_map[("department", r.id)] = {
                    "id": r.id, "name": r.name, "type": "department",
                    "department_id": r.id, "owner_id": r.owner_id,
                    "visibility": r.visibility,
                }
        if proj_ids:
            rows = (await session.scalars(select(Project).where(Project.id.in_(proj_ids)))).all()
            for r in rows:
                obj_map[("project", r.id)] = {
                    "id": r.id, "name": r.name, "type": "project",
                    "department_id": r.department_id, "owner_id": r.owner_id,
                    "visibility": r.visibility,
                }
        if doc_ids:
            rows = (await session.scalars(select(Document).where(Document.id.in_(doc_ids)))).all()
            for r in rows:
                obj_map[("document", r.id)] = {
                    "id": r.id, "name": r.name, "type": "document",
                    "department_id": r.department_id, "owner_id": r.owner_id,
                    "visibility": r.visibility, "project_id": r.project_id,
                }

    return [obj_map.get((rtype, rid)) for rtype, rid in keys]


async def all_documents_loader(keys: list[bool]):
    """Load all documents. keys is [True] — dummy for DataLoader interface."""
    _count("all_documents_loader")
    from .models import Document
    from sqlalchemy import select

    async with session_factory() as session:
        result = await session.scalars(select(Document))
        rows = result.all()

    docs = [
        {"id": r.id, "name": r.name, "type": "document",
         "department_id": r.department_id, "owner_id": r.owner_id,
         "visibility": r.visibility, "project_id": r.project_id}
        for r in rows
    ]
    return [docs for _ in keys]


# ── Relationship loaders ──


async def user_departments_loader(user_ids: list[int]):
    """Batch load department IDs for each user. Returns list[list[int]]."""
    _count("user_departments_loader")
    from .models import UserDepartment
    from sqlalchemy import select

    async with session_factory() as session:
        result = await session.scalars(
            select(UserDepartment).where(UserDepartment.user_id.in_(user_ids))
        )
        rows = result.all()

    grouped: dict[int, list[int]] = defaultdict(list)
    for ud in rows:
        grouped[ud.user_id].append(ud.department_id)
    return [grouped.get(uid, []) for uid in user_ids]


async def user_roles_loader(user_ids: list[int]):
    """Batch load roles for each user. Returns list[list[RoleRow]]."""
    _count("user_roles_loader")
    from .models import Role, UserRole
    from sqlalchemy import select

    async with session_factory() as session:
        result = await session.execute(
            select(UserRole, Role)
            .join(Role, UserRole.role_id == Role.id)
            .where(UserRole.user_id.in_(user_ids))
        )
        rows = result.all()

    grouped = defaultdict(list)
    for ur, role in rows:
        grouped[ur.user_id].append(role)
    return [grouped.get(uid, []) for uid in user_ids]


async def role_permissions_loader(role_ids: list[int]):
    """Batch load permissions (with conditions) for each role. Returns list[list]."""
    _count("role_permissions_loader")
    from .models import Permission, RolePermission
    from sqlalchemy import select

    async with session_factory() as session:
        result = await session.execute(
            select(RolePermission, Permission)
            .join(Permission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id.in_(role_ids))
        )
        rows = result.all()

    grouped = defaultdict(list)
    for rp, perm in rows:
        grouped[rp.role_id].append({
            "permission_id": perm.id,
            "permission_name": perm.name,
            "action": perm.action,
            "resource_type": perm.resource_type,
            "resource_type_ref": rp.resource_type,
            "resource_id": rp.resource_id,
            "effect": rp.effect,
            "conditions": rp.conditions,
        })
    return [grouped.get(rid, []) for rid in role_ids]


async def department_projects_loader(dept_ids: list[int]):
    """Batch load projects for each department."""
    _count("department_projects_loader")
    from .models import Project
    from sqlalchemy import select

    async with session_factory() as session:
        result = await session.scalars(
            select(Project).where(Project.department_id.in_(dept_ids))
        )
        rows = result.all()

    grouped = defaultdict(list)
    for r in rows:
        grouped[r.department_id].append({
            "id": r.id, "name": r.name, "type": "project",
            "department_id": r.department_id,
            "owner_id": r.owner_id,
            "visibility": r.visibility,
        })
    return [grouped.get(did, []) for did in dept_ids]


async def project_documents_loader(project_ids: list[int]):
    """Batch load documents for each project."""
    _count("project_documents_loader")
    from .models import Document
    from sqlalchemy import select

    async with session_factory() as session:
        result = await session.scalars(
            select(Document).where(Document.project_id.in_(project_ids))
        )
        rows = result.all()

    grouped = defaultdict(list)
    for r in rows:
        grouped[r.project_id].append({
            "id": r.id, "name": r.name, "type": "document",
            "department_id": r.department_id,
            "owner_id": r.owner_id,
            "visibility": r.visibility,
            "project_id": r.project_id,
        })
    return [grouped.get(pid, []) for pid in project_ids]


# ── Permission check loaders ──


async def mail_groups_loader(user_ids: list[int]):
    """Batch load mail groups for users via third-party API."""
    _count("mail_groups_loader")
    from .mailgroup_api import get_mail_groups_by_user

    results = []
    for uid in user_ids:
        groups = await get_mail_groups_by_user(uid)
        results.append(groups)
    return results


async def _get_ancestors(session, resource_type: str, resource_ids: list[int]) -> set[tuple[str, int]]:
    """Trace ancestor chain via FK lookups. Returns set of (type, id) including self.

    document → project → department
    project  → department
    department has no ancestors.
    """
    from sqlalchemy import select as sa_select

    ancestors = set()
    for rid in resource_ids:
        ancestors.add((resource_type, rid))

    if resource_type == "document":
        from .models import Document, Project
        docs = (await session.scalars(
            sa_select(Document).where(Document.id.in_(resource_ids))
        )).all()
        project_ids = list({d.project_id for d in docs})
        for pid in project_ids:
            ancestors.add(("project", pid))
        if project_ids:
            projs = (await session.scalars(
                sa_select(Project).where(Project.id.in_(project_ids))
            )).all()
            for p in projs:
                ancestors.add(("department", p.department_id))

    elif resource_type == "project":
        from .models import Project
        projs = (await session.scalars(
            sa_select(Project).where(Project.id.in_(resource_ids))
        )).all()
        for p in projs:
            ancestors.add(("department", p.department_id))

    return ancestors


async def candidate_permissions_loader(keys: list[tuple[int, str, int, str]]):
    """Batch load candidate permissions for (user_id, resource_type, resource_id, action).

    Two permission sources are merged:
    1. Direct: user → UserRole → RolePermission → Permission
    2. Group:  user → MailGroup (3rd party) → GroupRole → RolePermission → Permission

    Ancestor tracing uses sequential FK lookups (document→project→department).

    Returns list[list[dict]] — one list of candidate permissions per key.
    """
    _count("candidate_permissions_loader")
    from .models import GroupRole, Permission, RolePermission, UserRole
    from sqlalchemy import select, or_

    # Group by (user_id, action) to batch more efficiently
    user_action_groups: dict[tuple[int, str], list[tuple[str, int]]] = defaultdict(list)
    key_to_idx: dict[tuple[int, str, int, str], int] = {}

    for idx, (user_id, res_type, res_id, action) in enumerate(keys):
        ua = (user_id, action)
        user_action_groups[ua].append((res_type, res_id))
        key_to_idx[(user_id, res_type, res_id, action)] = idx

    results: list[list[dict]] = [[] for _ in keys]

    async with session_factory() as session:
        # ── Step 1: Trace ancestors for all resources ──
        all_ancestors: dict[tuple[int, str], set[tuple[str, int]]] = {}
        for (user_id, action), resource_keys in user_action_groups.items():
            # Group resources by type for batch ancestor tracing
            by_type: dict[str, list[int]] = defaultdict(list)
            for rtype, rid in resource_keys:
                by_type[rtype].append(rid)

            for rtype, rids in by_type.items():
                ancestor_set = await _get_ancestors(session, rtype, rids)
                for (rt, ri) in ancestor_set:
                    all_ancestors.setdefault((user_id, action), set()).add((rt, ri))

        # ── Step 2: Direct user → role permissions ──
        for (user_id, action), resource_keys in user_action_groups.items():
            ancestors = all_ancestors.get((user_id, action), set())

            # Collect unique target resource types for Permission.resource_type filter
            unique_rtypes = list({rtype for rtype, _rid in resource_keys})

            # 2a: Ancestor-matched permissions (resource-specific)
            if ancestors:
                # Build OR conditions for (resource_type, resource_id) pairs
                conditions = []
                for (rt, ri) in ancestors:
                    conditions.append(
                        (RolePermission.resource_type == rt) & (RolePermission.resource_id == ri)
                    )

                stmt = (
                    select(
                        RolePermission.id.label("rp_id"),
                        RolePermission.effect,
                        RolePermission.conditions,
                        RolePermission.resource_type.label("rp_resource_type"),
                        RolePermission.resource_id.label("rp_resource_id"),
                        Permission.id.label("perm_id"),
                        Permission.name.label("perm_name"),
                        Permission.action,
                        Permission.resource_type,
                    )
                    .select_from(UserRole)
                    .join(RolePermission, UserRole.role_id == RolePermission.role_id)
                    .join(Permission, RolePermission.permission_id == Permission.id)
                    .where(
                        UserRole.user_id == user_id,
                        Permission.action.in_([action, "admin"]),
                        or_(Permission.resource_type == "*", Permission.resource_type.in_(unique_rtypes)),
                        or_(*conditions),
                    )
                )
                rows = (await session.execute(stmt)).all()
                for row in rows:
                    # Map back: find which resources have this ancestor
                    for (rtype, rid) in resource_keys:
                        key = (user_id, rtype, rid, action)
                        if key in key_to_idx and (row.rp_resource_type, row.rp_resource_id) in all_ancestors.get((user_id, action), set()):
                            # Skip if Permission.resource_type doesn't match target
                            if row.resource_type != "*" and row.resource_type != rtype:
                                continue
                            results[key_to_idx[key]].append({
                                "role_permission_id": row.rp_id,
                                "permission_id": row.perm_id,
                                "permission_name": row.perm_name,
                                "action": row.action,
                                "resource_type": row.resource_type,
                                "effect": row.effect,
                                "conditions": row.conditions,
                                "matched_via": "direct-ancestor",
                            })

            # 2b: Global permissions (resource_type IS NULL, resource_id IS NULL)
            stmt2 = (
                select(
                    RolePermission.id.label("rp_id"),
                    RolePermission.effect,
                    RolePermission.conditions,
                    Permission.id.label("perm_id"),
                    Permission.name.label("perm_name"),
                    Permission.action,
                    Permission.resource_type,
                )
                .select_from(UserRole)
                .join(RolePermission, UserRole.role_id == RolePermission.role_id)
                .join(Permission, RolePermission.permission_id == Permission.id)
                .where(
                    UserRole.user_id == user_id,
                    Permission.action.in_([action, "admin"]),
                    or_(Permission.resource_type == "*", Permission.resource_type.in_(unique_rtypes)),
                    RolePermission.resource_type.is_(None),
                    RolePermission.resource_id.is_(None),
                )
            )
            rows2 = (await session.execute(stmt2)).all()
            for row in rows2:
                for (rtype, rid) in resource_keys:
                    key = (user_id, rtype, rid, action)
                    if key in key_to_idx:
                        # Skip if Permission.resource_type doesn't match target
                        if row.resource_type != "*" and row.resource_type != rtype:
                            continue
                        results[key_to_idx[key]].append({
                            "role_permission_id": row.rp_id,
                            "permission_id": row.perm_id,
                            "permission_name": row.perm_name,
                            "action": row.action,
                            "resource_type": row.resource_type,
                            "effect": row.effect,
                            "conditions": row.conditions,
                            "matched_via": "direct-global",
                        })

        # ── Step 3: Group-inherited permissions (via MailGroup → GroupRole) ──
        from .mailgroup_api import get_mail_groups_by_user

        user_group_map: dict[int, list[int]] = {}
        for (uid, _act) in user_action_groups:
            if uid not in user_group_map:
                groups = await get_mail_groups_by_user(uid)
                user_group_map[uid] = [g["id"] for g in groups]

        for (user_id, action), resource_keys in user_action_groups.items():
            group_ids = user_group_map.get(user_id, [])
            if not group_ids:
                continue

            ancestors = all_ancestors.get((user_id, action), set())

            # Collect unique target resource types for Permission.resource_type filter
            unique_rtypes = list({rtype for rtype, _rid in resource_keys})

            # 3a: Ancestor-matched permissions
            if ancestors:
                conditions = []
                for (rt, ri) in ancestors:
                    conditions.append(
                        (RolePermission.resource_type == rt) & (RolePermission.resource_id == ri)
                    )

                stmt3 = (
                    select(
                        RolePermission.id.label("rp_id"),
                        RolePermission.effect,
                        RolePermission.conditions,
                        RolePermission.resource_type.label("rp_resource_type"),
                        RolePermission.resource_id.label("rp_resource_id"),
                        Permission.id.label("perm_id"),
                        Permission.name.label("perm_name"),
                        Permission.action,
                        Permission.resource_type,
                    )
                    .select_from(GroupRole)
                    .join(RolePermission, GroupRole.role_id == RolePermission.role_id)
                    .join(Permission, RolePermission.permission_id == Permission.id)
                    .where(
                        GroupRole.group_id.in_(group_ids),
                        Permission.action.in_([action, "admin"]),
                        or_(Permission.resource_type == "*", Permission.resource_type.in_(unique_rtypes)),
                        or_(*conditions),
                    )
                )
                rows3 = (await session.execute(stmt3)).all()
                for row in rows3:
                    for (rtype, rid) in resource_keys:
                        key = (user_id, rtype, rid, action)
                        if key in key_to_idx and (row.rp_resource_type, row.rp_resource_id) in ancestors:
                            # Skip if Permission.resource_type doesn't match target
                            if row.resource_type != "*" and row.resource_type != rtype:
                                continue
                            results[key_to_idx[key]].append({
                                "role_permission_id": row.rp_id,
                                "permission_id": row.perm_id,
                                "permission_name": row.perm_name,
                                "action": row.action,
                                "resource_type": row.resource_type,
                                "effect": row.effect,
                                "conditions": row.conditions,
                                "matched_via": "group-ancestor",
                            })

            # 3b: Global permissions
            stmt4 = (
                select(
                    RolePermission.id.label("rp_id"),
                    RolePermission.effect,
                    RolePermission.conditions,
                    Permission.id.label("perm_id"),
                    Permission.name.label("perm_name"),
                    Permission.action,
                    Permission.resource_type,
                )
                .select_from(GroupRole)
                .join(RolePermission, GroupRole.role_id == RolePermission.role_id)
                .join(Permission, RolePermission.permission_id == Permission.id)
                .where(
                    GroupRole.group_id.in_(group_ids),
                    Permission.action.in_([action, "admin"]),
                    or_(Permission.resource_type == "*", Permission.resource_type.in_(unique_rtypes)),
                    RolePermission.resource_type.is_(None),
                    RolePermission.resource_id.is_(None),
                )
            )
            rows4 = (await session.execute(stmt4)).all()
            for row in rows4:
                for (rtype, rid) in resource_keys:
                    key = (user_id, rtype, rid, action)
                    if key in key_to_idx:
                        # Skip if Permission.resource_type doesn't match target
                        if row.resource_type != "*" and row.resource_type != rtype:
                            continue
                        results[key_to_idx[key]].append({
                            "role_permission_id": row.rp_id,
                            "permission_id": row.perm_id,
                            "permission_name": row.perm_name,
                            "action": row.action,
                            "resource_type": row.resource_type,
                            "effect": row.effect,
                            "conditions": row.conditions,
                            "matched_via": "group-global",
                        })

    return results
