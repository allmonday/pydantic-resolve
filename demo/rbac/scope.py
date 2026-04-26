"""Scope tree computation and injection hook for RBAC demo.

Provides:
- compute_scope_tree: Build scope tree via Resolver + AutoLoad
- inject_access_scope: resolved_hook for scope propagation

Scope tree format (_access_scope_tree):
- None: no scope constraint (default)
- list[ScopeNode]: scoped access, each node has is_all/ids/filter_fn/children
  - []: no permission (empty)
  - [ScopeNode(is_all=True)]: global permission, unconstrained
  - [ScopeNode(ids=[1,2])]: scoped access with specific IDs

Relationships are declared in entities.py and traversed via AutoLoad.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel

from pydantic_resolve import ICollector, Loader, Resolver, SendTo
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
    if not scope_tree:
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
        children = entry.children
        if entry.is_all or entry.ids is None:
            # Unconstrained → all items get same children
            for item in items:
                iid = getattr(item, 'id', None)
                if iid is not None and children:
                    id_to_children.setdefault(iid, []).extend(children)
        else:
            for iid in entry.ids:
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
# Custom collector for scope computation
# =====================================


class RolePermDedupCollector(ICollector):
    """Collect ScopeRolePermView with deduplication by (role_id, permission_id)."""

    def __init__(self, alias: str):
        self.alias = alias
        self._seen: set[tuple[int, int]] = set()
        self._result: list = []

    def add(self, val):
        items = val if isinstance(val, list) else [val]
        for item in items:
            key = (item.role_id, item.permission_id)
            if key not in self._seen:
                self._seen.add(key)
                self._result.append(item)

    def values(self) -> list:
        return self._result


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
    """Role with role_permissions auto-loaded and sent to collector."""
    role_permissions: Annotated[list[ScopeRolePermView], AutoLoad(), SendTo('all_perms')] = []


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
    scope_tree: list[ScopeNode] = []

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

    async def post_scope_tree(self, collector=RolePermDedupCollector('all_perms')):
        """Aggregate all permissions and build scope tree.

        RolePermDedupCollector auto-collects from ScopeRoleView.role_permissions
        via SendTo, covering both user_roles and group_roles chains.
        """
        all_perms = collector.values()
        if not all_perms:
            return []

        # 2. Filter: effect=allow, action matches
        filtered = [
            rp for rp in all_perms
            if rp.effect == "allow"
            and rp.permission
            and rp.permission.action in (self.action, "admin")
        ]

        if not filtered:
            return []

        # 3. Check for global permissions (resource_type is None AND resource_id is None)
        global_perms = [
            rp for rp in filtered
            if rp.resource_type is None and rp.resource_id is None
        ]

        if global_perms:
            unconditional = [rp for rp in global_perms if rp.condition is None]
            if unconditional:
                return [ScopeNode(type=HIERARCHY[0].relationship_name, is_all=True)]
            return await self._build_global_scope(global_perms)

        # 4. Build scope tree from resource-scoped permissions
        return await self._build_resource_scope(filtered)

    async def _build_global_scope(self, global_perms):
        """Build scope tree for global permissions with named conditions."""
        from .condition import get_condition

        subject = {'department_ids': self.department_ids, 'user_id': self.user_id}

        merged_ids: set[int] = set()
        merged_filter_fn = None
        for rp in global_perms:
            cond = get_condition(rp.condition)
            if not cond:
                continue
            ids, filter_fn = cond.build_scope(subject)
            if ids:
                merged_ids.update(ids)
            if filter_fn:
                merged_filter_fn = filter_fn

        if not merged_ids and not merged_filter_fn:
            return []

        return [ScopeNode(
            type=HIERARCHY[0].relationship_name,
            ids=sorted(merged_ids) if merged_ids else None,
            filter_fn=merged_filter_fn,
            children=None,
        )]

    async def _build_resource_scope(self, filtered):
        """Build flat scope nodes from resource-scoped permissions.

        Each authorized level produces a direct ScopeNode at the root of the tree.
        No implicit ancestor tracing.
        """
        nodes = []
        for lvl in HIERARCHY:
            ids = sorted({
                rp.resource_id for rp in filtered
                if rp.resource_type == lvl.resource_type and rp.resource_id is not None
            })
            if ids:
                nodes.append(ScopeNode(type=lvl.relationship_name, ids=ids))
        return nodes


# =====================================
# compute_scope_tree wrapper
# =====================================


async def compute_scope_tree(user_id: int, action: str = "read") -> list[ScopeNode]:
    """Build scope tree for user+action using Resolver + AutoLoad.

    Returns list[ScopeNode]:
    - []: no permission
    - [ScopeNode(is_all=True)]: global permission, unconstrained
    - [ScopeNode(ids=[...])]: scoped access
    """
    view = ScopeComputeView(user_id=user_id, action=action)
    view = await Resolver(enable_from_attribute_in_type_adapter=True).resolve(view)
    return view.scope_tree
