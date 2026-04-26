"""Pydantic response models with resolve_*/post_* for RBAC/ABAC demo."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict

from pydantic_resolve import ExposeAs, Loader

from .condition import evaluate_condition
from .loaders import (
    all_documents_loader,
    candidate_permissions_loader,
    department_projects_loader,
    mail_groups_loader,
    project_documents_loader,
    resources_by_keys_loader,
    role_permissions_loader,
    user_departments_loader,
    user_roles_loader,
)


# ── Basic views ──


class RoleBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


# ── Scenario A: User permission expansion (dashboard) ──


class PermissionView(BaseModel):
    permission_id: int
    permission_name: str
    action: str
    resource_type: str
    resource_type_ref: str | None = None
    resource_id: int | None = None
    effect: str
    conditions: dict | None = None


class RoleWithPerms(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    permissions: list[PermissionView] = []

    def resolve_permissions(self, loader=Loader(role_permissions_loader)):
        return loader.load(self.id)


class UserPermissionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    level: int
    department_ids: list[int] = []
    roles: list[RoleWithPerms] = []

    def resolve_department_ids(self, loader=Loader(user_departments_loader)):
        return loader.load(self.id)

    def resolve_roles(self, loader=Loader(user_roles_loader)):
        return loader.load(self.id)


# ── Scenario B: Resource access check with ABAC ──


class CandidatePerm(BaseModel):
    role_permission_id: int
    permission_id: int
    permission_name: str
    action: str
    resource_type: str
    effect: str
    condition: str | None = None
    matched_via: str = ""


class ResourceAccessView(BaseModel):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
    id: int
    name: str
    type: str
    department_id: int | None = None
    owner_id: int | None = None
    visibility: str = "internal"

    # DataLoader: SQL coarse filter — batch load candidate permissions
    candidate_perms: list[CandidatePerm] = []

    def resolve_candidate_perms(
        self,
        loader=Loader(candidate_permissions_loader),
        ancestor_context=None,
    ):
        ctx = ancestor_context or {}
        user_id = ctx.get("check_user_id", 0)
        action = ctx.get("check_action", "read")
        return loader.load((user_id, self.type, self.id, action))

    # post_*: ABAC fine filter — evaluate conditions in application layer
    accessible: bool = False
    access_reason: str = ""
    matched_rule: str = ""

    def post_accessible(self, ancestor_context=None):
        ctx = ancestor_context or {}
        if not self.candidate_perms:
            self.access_reason = "No matching permissions found"
            return False

        subject_attrs = {
            "department_ids": ctx.get("check_user_depts", []),
            "level": ctx.get("check_user_level", 0),
            "id": ctx.get("check_user_id", 0),
        }
        resource_attrs = {
            "department_id": self.department_id,
            "owner_id": self.owner_id,
            "visibility": self.visibility,
            "type": self.type,
        }

        for perm in self.candidate_perms:
            if perm.effect != "allow":
                continue

            if perm.condition is None:
                self.matched_rule = perm.permission_name
                self.access_reason = f"Allowed by {perm.permission_name} (unconditional)"
                return True

            if evaluate_condition(perm.condition, subject_attrs, resource_attrs):
                self.matched_rule = perm.permission_name
                self.access_reason = f"Allowed by {perm.permission_name} (condition: {perm.condition})"
                return True

        self.access_reason = "No allow rule matched conditions"
        return False


class AccessCheckRequest(BaseModel):
    """Top-level model for checking access to multiple resources."""
    user_id: Annotated[int, ExposeAs("check_user_id")]
    user_depts: Annotated[list[int], ExposeAs("check_user_depts")]
    user_level: Annotated[int, ExposeAs("check_user_level")]
    action: Annotated[str, ExposeAs("check_action")]
    # (resource_type, resource_id) pairs to check
    target_resources: list[tuple[str, int]] = []
    resources: list[ResourceAccessView] = []

    async def resolve_resources(self):
        """Load resources and return as dicts for Resolver to convert."""
        resources = await resources_by_keys_loader(self.target_resources)
        return resources


# ── Scenario C: Resource tree (Dept → Project → Document) ──


class DocumentNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    department_id: int
    owner_id: int | None = None
    visibility: str = "internal"
    project_id: int | None = None


class ProjectNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    department_id: int
    owner_id: int | None = None
    visibility: str = "internal"
    documents: list[DocumentNode] = []

    def resolve_documents(self, loader=Loader(project_documents_loader)):
        return loader.load(self.id)


class DepartmentNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    owner_id: int | None = None
    visibility: str = "internal"
    projects: list[ProjectNode] = []

    def resolve_projects(self, loader=Loader(department_projects_loader)):
        return loader.load(self.id)


# ── Scenario D: Document list with batch permission check ──


class DocumentWithAccess(BaseModel):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
    id: int
    name: str
    department_id: int | None = None
    owner_id: int | None = None
    visibility: str = "internal"

    candidate_perms: list[CandidatePerm] = []

    def resolve_candidate_perms(
        self,
        loader=Loader(candidate_permissions_loader),
        ancestor_context=None,
    ):
        ctx = ancestor_context or {}
        user_id = ctx.get("check_user_id", 0)
        action = ctx.get("check_action", "read")
        return loader.load((user_id, "document", self.id, action))

    can_read: bool = False
    can_write: bool = False
    access_reason: str = ""

    def post_can_read(self, ancestor_context=None):
        return self._check_access("read", ancestor_context)

    def post_can_write(self, ancestor_context=None):
        return self._check_access("write", ancestor_context)

    def post_access_reason(self):
        if self.can_read and self.can_write:
            return "Full access"
        elif self.can_read:
            return "Read only"
        return "No access"

    def _check_access(self, action: str, ancestor_context=None) -> bool:
        ctx = ancestor_context or {}
        subject_attrs = {
            "department_ids": ctx.get("check_user_depts", []),
            "level": ctx.get("check_user_level", 0),
            "id": ctx.get("check_user_id", 0),
        }
        resource_attrs = {
            "department_id": self.department_id,
            "owner_id": self.owner_id,
            "visibility": self.visibility,
        }

        for perm in self.candidate_perms:
            if perm.effect != "allow":
                continue
            if perm.action != action and perm.action != "admin":
                continue
            if evaluate_condition(perm.condition, subject_attrs, resource_attrs):
                return True
        return False


class DocumentListView(BaseModel):
    """List all documents with permission checks for a user."""
    user_id: Annotated[int, ExposeAs("check_user_id")]
    user_depts: Annotated[list[int], ExposeAs("check_user_depts")]
    user_level: Annotated[int, ExposeAs("check_user_level")]
    documents: list[DocumentWithAccess] = []

    async def resolve_documents(self):
        docs = await all_documents_loader([True])
        return docs[0] if docs else []


# ── Scenario E: Mail group-aware permission view ──


class MailGroupBrief(BaseModel):
    id: int
    name: str
    email: str


class UserPermissionWithGroupsView(BaseModel):
    """Like UserPermissionView but also shows mail groups the user belongs to."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    level: int
    department_ids: list[int] = []
    mail_groups: list[MailGroupBrief] = []
    roles: list[RoleWithPerms] = []

    def resolve_department_ids(self, loader=Loader(user_departments_loader)):
        return loader.load(self.id)

    def resolve_mail_groups(self, loader=Loader(mail_groups_loader)):
        return loader.load(self.id)

    def resolve_roles(self, loader=Loader(user_roles_loader)):
        return loader.load(self.id)


# ── Scenario F: Scope pre-constraint (ER Diagram + AutoLoad + scope) ──


from .entities import AutoLoad, DepartmentEntity, DocumentEntity, ProjectEntity, UserEntity


class DocumentScopeView(DocumentEntity):
    """Document view for scope-constrained loading."""
    pass


class ProjectScopeView(ProjectEntity):
    """Project view with scope-constrained document loading."""
    documents: Annotated[list[DocumentScopeView], AutoLoad()] = []


class DepartmentScopeView(DepartmentEntity):
    """Department view with scope-constrained project loading."""
    projects: Annotated[list[ProjectScopeView], AutoLoad()] = []


class UserScopeView(UserEntity):
    """Root view: user -> departments via scope-aware AutoLoad.

    All levels (user → departments → projects → documents) use AutoLoad + scope.
    The _access_scope_tree determines which departments the user can access:
    - 'all': global permission, unconstrained
    - 'empty': no permission
    - [{'type':'departments','ids':[1],'children':[...]}]: scoped with nested constraints
    """
    departments: Annotated[list[DepartmentScopeView], AutoLoad()] = []
