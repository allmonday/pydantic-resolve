"""User scope computation and injection hook for RBAC demo.

Provides:
- compute_user_scope: Build user scope dict via Resolver + AutoLoad
- inject_user_scope: resolved_hook for scope propagation

User scope format (_user_scope):
- None: scope system not active (default)
- dict[str, ScopeFilter]: flat map keyed by relationship name
  - {}: no permission at any level
  - {"departments": ScopeFilter(is_all=True)}: global permission
  - {"projects": ScopeFilter(ids=frozenset({1}))}: scoped access

Relationships are declared in entities.py and traversed via AutoLoad.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel

from pydantic_resolve import ICollector, Loader, Resolver, SendTo
from pydantic_resolve.types import ScopeFilter

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
# ScopeRegistry — resource_type → scope_key mapping
# =====================================


@dataclass(frozen=True)
class ScopeRegistryEntry:
    """Maps a permission resource_type to scope dict key and entity."""

    resource_type: str    # "project" — matches RolePermission.resource_type
    scope_key: str        # "projects" — matches AutoLoad field name
    entity_kls: type      # ProjectEntity — for validation


class ScopeRegistry:
    """Central registry for scope resource mapping.

    Single source of truth mapping permission resource_type strings
    to scope dict keys (relationship/AutoLoad field names) and entity classes.
    """

    def __init__(self):
        self._entries: list[ScopeRegistryEntry] = []
        self._by_resource_type: dict[str, ScopeRegistryEntry] = {}

    def register(self, resource_type: str, scope_key: str, entity_kls: type):
        entry = ScopeRegistryEntry(resource_type, scope_key, entity_kls)
        self._entries.append(entry)
        self._by_resource_type[resource_type] = entry

    @property
    def entries(self) -> list[ScopeRegistryEntry]:
        return self._entries

    def scope_key_for(self, resource_type: str) -> str | None:
        entry = self._by_resource_type.get(resource_type)
        return entry.scope_key if entry else None


scope_registry = ScopeRegistry()
scope_registry.register("department", "departments", DepartmentEntity)
scope_registry.register("project",    "projects",    ProjectEntity)
scope_registry.register("document",   "documents",   DocumentEntity)


# inject_user_scope resolved-hook is no longer needed.
# Scope is now passed via Resolver context={"_user_scope": scope_dict}
# and read directly by AutoLoad-generated resolve methods.


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
    """Root model for computing user scope via Resolver + AutoLoad.

    resolve_* loads initial data, AutoLoad traverses entity chain,
    post_user_scope aggregates and builds the flat scope dict.
    """
    user_id: int
    action: str = "read"

    # Pre-loaded for ABAC condition evaluation
    department_ids: list[int] = []

    # Direct roles — loaded via resolve_*, then AutoLoad traverses chain
    user_roles: list[ScopeUserRoleView] = []

    # Group-inherited roles — external API + resolve_*, then AutoLoad
    group_roles: list[ScopeGroupRoleView] = []

    # Final result: flat dict mapping scope_key → ScopeFilter
    user_scope: dict[str, ScopeFilter] = {}

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

    async def post_user_scope(self, collector=RolePermDedupCollector('all_perms')):
        """Aggregate all permissions and build user scope dict.

        RolePermDedupCollector auto-collects from ScopeRoleView.role_permissions
        via SendTo, covering both user_roles and group_roles chains.
        """
        all_perms = collector.values()
        if not all_perms:
            return {}

        # Filter: effect=allow, action matches
        filtered = [
            rp for rp in all_perms
            if rp.effect == "allow"
            and rp.permission
            and rp.permission.action in (self.action, "admin")
        ]

        if not filtered:
            return {}

        # Check for global permissions (resource_type is None AND resource_id is None)
        global_perms = [
            rp for rp in filtered
            if rp.resource_type is None and rp.resource_id is None
        ]

        if global_perms:
            unconditional = [rp for rp in global_perms if rp.condition is None]
            if unconditional:
                # Global admin: all levels unconstrained
                return {e.scope_key: ScopeFilter(is_all=True) for e in scope_registry.entries}
            return await self._build_global_scope(global_perms)

        # Build scope from resource-scoped permissions
        return await self._build_resource_scope(filtered)

    async def _build_global_scope(self, global_perms):
        """Build scope dict for global permissions with named conditions."""
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
            return {}

        ids = frozenset(merged_ids) if merged_ids else None
        return {"departments": ScopeFilter(ids=ids, filter_fn=merged_filter_fn)}

    async def _build_resource_scope(self, filtered):
        """Build flat scope dict from resource-scoped permissions.

        Each authorized level produces a direct entry in the dict.
        """
        result: dict[str, ScopeFilter] = {}
        for entry in scope_registry.entries:
            ids = frozenset({
                rp.resource_id for rp in filtered
                if rp.resource_type == entry.resource_type and rp.resource_id is not None
            })
            if ids:
                result[entry.scope_key] = ScopeFilter(ids=ids)
        return result


# =====================================
# compute_user_scope wrapper
# =====================================


async def compute_user_scope(user_id: int, action: str = "read") -> dict[str, ScopeFilter]:
    """Build user scope dict for user+action using Resolver + AutoLoad.

    Returns dict[str, ScopeFilter]:
    - {}: no permission
    - {"departments": ScopeFilter(is_all=True)}: global permission
    - {"projects": ScopeFilter(ids=frozenset({1}))}: scoped access
    """
    view = ScopeComputeView(user_id=user_id, action=action)
    view = await Resolver(enable_from_attribute_in_type_adapter=True).resolve(view)
    return view.user_scope


async def scope_provider(context: dict | None) -> dict[str, ScopeFilter]:
    """Adapter for ErDiagram.enable_scope(scope_provider=...).

    Extracts user_id/action from Resolver context and delegates to compute_user_scope.
    """
    if context is None:
        return {}
    user_id = context.get('user_id')
    if user_id is None:
        return {}
    action = context.get('action', 'read')
    return await compute_user_scope(user_id=user_id, action=action)
