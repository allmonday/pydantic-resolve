"""Scope tree computation and injection hook for RBAC demo.

Provides:
- compute_scope_tree: Build scope tree via Resolver + AutoLoad
- inject_access_scope: resolved_hook for scope propagation

Scope tree format (_access_scope_tree):
- None: no scope constraint (default)
- 'all': global permission, unconstrained loading
- 'empty': no permission, return empty
- list[ScopeNode]: scoped access with type/ids/apply/children

Relationships are declared in entities.py and traversed via AutoLoad.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel

from pydantic_resolve import Loader, Resolver
from pydantic_resolve.types import ScopeNode

from .entities import (
    AutoLoad,
    DepartmentEntity,
    DocumentEntity,
    GroupRoleEntity,
    PermissionEntity,
    ProjectEntity,
    RoleEntity,
    RolePermissionEntity,
    UserRoleEntity,
)
from .loaders import user_departments_loader, user_role_entities_loader


# =====================================
# Hierarchy descriptor
# =====================================


@dataclass(frozen=True)
class HierarchyLevel:
    """One level in the resource hierarchy.

    Attributes:
        resource_type: matches RolePermission.resource_type string
        relationship_name: ScopeNode.type value (matches AutoLoad field name)
        parent_fk_field: FK field on this entity pointing to parent; None for root
    """
    resource_type: str
    relationship_name: str
    parent_fk_field: str | None


# Single source of truth for the resource hierarchy.
# Adding a new level (e.g., Folder) only requires appending here.
HIERARCHY = [
    HierarchyLevel("department", "departments", None),
    HierarchyLevel("project",    "projects",    "department_id"),
    HierarchyLevel("document",   "documents",   "project_id"),
]

# Explicitly declared scope-relevant entities.
# NOT auto-derived — UserEntity has non-scope relationships (e.g., UserRole)
# that would cause false positives in alignment validation.
SCOPE_ENTRY_ENTITIES = [DepartmentEntity, ProjectEntity, DocumentEntity]


def validate_scope_alignment(
    hierarchy: list[HierarchyLevel],
    entry_entities: list[type],
) -> set[str]:
    """Validate that hierarchy levels are subset of declared entry entities.

    Convention: DepartmentEntity -> "department" (strip "Entity", lowercase).
    Returns set of unaligned resource_type strings (empty if valid).
    """
    declared_types = set()
    for cls in entry_entities:
        name = cls.__name__
        if name.endswith("Entity"):
            name = name[:-6]
        declared_types.add(name.lower())

    hierarchy_types = {lvl.resource_type for lvl in hierarchy}
    return hierarchy_types - declared_types


# =====================================
# inject_access_scope resolved-hook
# =====================================


def inject_access_scope(parent, field_name, result):
    """resolved-hook: propagate scope tree children to resolved items.

    Called after each resolve method, before recursive traversal.
    Reads _access_scope_tree from parent, finds entries matching field_name,
    and injects children into resolved items by item ID.
    """
    scope_tree = getattr(parent, '_access_scope_tree', None)
    if not scope_tree or scope_tree in ('all', 'empty'):
        return

    if not isinstance(scope_tree, list):
        return

    # Find entries matching current field_name
    matched = [e for e in scope_tree if e.type == field_name]
    if not matched:
        return

    items = _get_items(result)
    if not items:
        # Single object: merge children from all matched entries
        all_children = []
        for entry in matched:
            if entry.children:
                all_children.extend(entry.children)
        if all_children and hasattr(result, '__dict__'):
            object.__setattr__(result, '_access_scope_tree', all_children)
        return

    # List results: build map from item ID → children
    id_to_children: dict[int, list] = {}
    for entry in matched:
        entry_ids = entry.ids
        children = entry.children
        if entry_ids is None:
            # Unconstrained → all items get same children
            for item in items:
                iid = getattr(item, 'id', None)
                if iid is not None and children:
                    id_to_children.setdefault(iid, []).extend(children)
        else:
            for iid in entry_ids:
                if children:
                    id_to_children.setdefault(iid, []).extend(children)

    for item in items:
        iid = getattr(item, 'id', None)
        child_scope = id_to_children.get(iid)
        if child_scope is not None:
            object.__setattr__(item, '_access_scope_tree', child_scope)


def _get_items(result):
    """Extract items from result (list or paginated)."""
    items = getattr(result, 'items', None)
    if items:
        return items
    if isinstance(result, list):
        return result
    return None


# =====================================
# AutoLoad view model tree
# =====================================


class ScopePermView(PermissionEntity):
    """Permission entity for scope computation."""
    pass


class ScopeRolePermView(RolePermissionEntity):
    """RolePermission with permission auto-loaded."""
    permission: Annotated[ScopePermView | None, AutoLoad()] = None


class ScopeRoleView(RoleEntity):
    """Role with role_permissions auto-loaded."""
    role_permissions: Annotated[list[ScopeRolePermView], AutoLoad()] = []


class ScopeUserRoleView(UserRoleEntity):
    """UserRole with role auto-loaded."""
    role: Annotated[ScopeRoleView | None, AutoLoad()] = None


class ScopeGroupRoleView(GroupRoleEntity):
    """GroupRole with role auto-loaded."""
    role: Annotated[ScopeRoleView | None, AutoLoad()] = None


# =====================================
# ScopeComputeView — root model
# =====================================


class ScopeComputeView(BaseModel):
    """Root model for computing scope tree via Resolver + AutoLoad.

    resolve_* loads initial data, AutoLoad traverses entity chain,
    post_scope_tree aggregates and builds the scope tree.
    """
    user_id: int
    action: str = "read"

    # Pre-loaded for ABAC condition evaluation
    department_ids: list[int] = []

    # Direct roles — loaded via resolve_*, then AutoLoad traverses chain
    user_roles: list[ScopeUserRoleView] = []

    # Group-inherited roles — external API + resolve_*, then AutoLoad
    group_roles: list[ScopeGroupRoleView] = []

    # Final result
    scope_tree: str | list[ScopeNode] = 'empty'

    def resolve_department_ids(self, loader=Loader(user_departments_loader)):
        return loader.load(self.user_id)

    def resolve_user_roles(self, loader=Loader(user_role_entities_loader)):
        return loader.load(self.user_id)

    async def resolve_group_roles(self):
        from .loaders import group_role_entities_loader
        from .mailgroup_api import get_mail_groups_by_user

        groups = await get_mail_groups_by_user(self.user_id)
        group_ids = [g["id"] for g in groups]
        if not group_ids:
            return []
        batches = await group_role_entities_loader(group_ids)
        return [gr for batch in batches for gr in batch]

    async def post_scope_tree(self):
        """Aggregate all permissions and build scope tree."""
        # 1. Collect + deduplicate RolePermissionEntity from all roles
        seen: set[tuple[int, int]] = set()
        all_perms: list[ScopeRolePermView] = []

        for ur in self.user_roles:
            if ur.role:
                for rp in ur.role.role_permissions:
                    key = (rp.role_id, rp.permission_id)
                    if key not in seen:
                        seen.add(key)
                        all_perms.append(rp)

        for gr in self.group_roles:
            if gr.role:
                for rp in gr.role.role_permissions:
                    key = (rp.role_id, rp.permission_id)
                    if key not in seen:
                        seen.add(key)
                        all_perms.append(rp)

        if not all_perms:
            return 'empty'

        # 2. Filter: effect=allow, action matches
        filtered = [
            rp for rp in all_perms
            if rp.effect == "allow"
            and rp.permission
            and rp.permission.action in (self.action, "admin")
        ]

        if not filtered:
            return 'empty'

        # 3. Check for global permissions (resource_type is None AND resource_id is None)
        global_perms = [
            rp for rp in filtered
            if rp.resource_type is None and rp.resource_id is None
        ]

        if global_perms:
            unconditional = [rp for rp in global_perms if rp.condition is None]
            if unconditional:
                return 'all'
            return await self._build_global_scope(global_perms)

        # 4. Build scope tree from resource-scoped permissions
        return await self._build_resource_scope(filtered)

    async def _build_global_scope(self, global_perms):
        """Build scope tree for global permissions with named conditions."""
        from .condition import get_condition

        subject = {'department_ids': self.department_ids, 'user_id': self.user_id}

        merged_ids: set[int] = set()
        merged_apply = None
        for rp in global_perms:
            cond = get_condition(rp.condition)
            if not cond:
                continue
            ids, apply = cond.build_scope(subject)
            if ids:
                merged_ids.update(ids)
            if apply:
                merged_apply = apply

        if not merged_ids and not merged_apply:
            return 'empty'

        return [ScopeNode(
            type=HIERARCHY[0].relationship_name,
            ids=sorted(merged_ids) if merged_ids else None,
            apply=merged_apply,
            children=None,
        )]

    async def _build_resource_scope(self, filtered):
        """Build scope tree from resource-scoped permissions."""
        from .loaders import _make_mapping_loader, _resolve_orm_model

        # 4a: Group resource_ids by type (driven by HIERARCHY)
        valid_types = {lvl.resource_type for lvl in HIERARCHY}
        direct_ids_by_type: dict[str, set[int]] = {lvl.resource_type: set() for lvl in HIERARCHY}

        for rp in filtered:
            rt = rp.resource_type
            ri = rp.resource_id
            if rt in valid_types and ri is not None:
                direct_ids_by_type[rt].add(ri)

        if not any(direct_ids_by_type.values()):
            return 'empty'

        # 4b: Resolve FK chains via generic mapping loaders
        fk_chain: dict[str, dict[int, int]] = {}
        for lvl in HIERARCHY[1:]:
            ids = direct_ids_by_type.get(lvl.resource_type, set())
            if not ids or not lvl.parent_fk_field:
                continue
            orm_model = _resolve_orm_model(lvl.resource_type)
            loader = _make_mapping_loader(orm_model, lvl.parent_fk_field)
            parent_ids = await loader(sorted(ids))
            fk_chain[lvl.resource_type] = {
                cid: pid
                for cid, pid in zip(sorted(ids), parent_ids)
                if pid is not None
            }

        # 4c: Trace all resource IDs to root level
        all_root_ids: set[int] = set()
        for i, lvl in enumerate(HIERARCHY):
            ids = direct_ids_by_type.get(lvl.resource_type, set())
            if not ids:
                continue
            if i == 0:
                all_root_ids.update(ids)
            else:
                current_ids = ids
                for j in range(i, 0, -1):
                    child_rt = HIERARCHY[j].resource_type
                    mapping = fk_chain.get(child_rt, {})
                    current_ids = {mapping[cid] for cid in current_ids if cid in mapping}
                all_root_ids.update(current_ids)

        if not all_root_ids:
            return 'empty'

        # 4d: Build scope tree
        return _build_scope_tree(HIERARCHY, all_root_ids, direct_ids_by_type, fk_chain)


# =====================================
# compute_scope_tree wrapper
# =====================================


async def compute_scope_tree(user_id: int, action: str = "read") -> str | list[ScopeNode]:
    """Build scope tree for user+action using Resolver + AutoLoad.

    Returns:
    - 'all': global permission, no constraint
    - 'empty': no permission
    - list[ScopeNode]: scoped access as list-of-nodes
    """
    view = ScopeComputeView(user_id=user_id, action=action)
    view = await Resolver(enable_from_attribute_in_type_adapter=True).resolve(view)
    return view.scope_tree


# =====================================
# Scope tree builder
# =====================================


def _build_scope_tree(
    hierarchy: list[HierarchyLevel],
    all_root_ids: set[int],
    direct_ids_by_type: dict[str, set[int]],
    fk_chain: dict[str, dict[int, int]],
) -> list[ScopeNode]:
    """Build list[ScopeNode] recursively from hierarchy descriptor."""

    root = hierarchy[0]

    def _children(level_idx: int, parent_id: int) -> list[ScopeNode] | None:
        """Build child ScopeNodes for a parent entity at level_idx-1."""
        if level_idx >= len(hierarchy):
            return None

        lvl = hierarchy[level_idx]
        mapping = fk_chain.get(lvl.resource_type, {})
        child_ids = sorted(cid for cid, pid in mapping.items() if pid == parent_id)

        if not child_ids:
            return None

        nodes = []
        for cid in child_ids:
            has_direct = cid in direct_ids_by_type.get(lvl.resource_type, set())
            nodes.append(ScopeNode(
                type=lvl.relationship_name,
                ids=[cid],
                children=None if has_direct else _children(level_idx + 1, cid),
            ))
        return nodes

    # Build root-level nodes
    nodes = []
    for rid in sorted(all_root_ids):
        has_direct = rid in direct_ids_by_type.get(root.resource_type, set())
        nodes.append(ScopeNode(
            type=root.relationship_name,
            ids=[rid],
            children=None if has_direct else _children(1, rid),
        ))
    return nodes
