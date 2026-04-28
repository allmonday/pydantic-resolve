"""ER Diagram entities for RBAC scope demo.

Defines entity relationships for AutoLoad-driven data loading.
Includes both resource hierarchy and permission model entities.
"""

from pydantic import BaseModel
from pydantic_resolve import Relationship, base_entity, config_global_resolver

from .loaders import (
    departments_loader,
    department_projects_loader,
    permission_by_id_loader,
    project_documents_loader,
    projects_loader,
    role_loader,
    role_permission_rows_loader,
    role_permissions_loader,
    user_departments_by_scope_loader,
    user_documents_by_scope_loader,
    user_projects_by_scope_loader,
)

BaseEntity = base_entity()


# ── Resource entities ──


class DocumentEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(
            fk='project_id',
            name='project',
            target='ProjectEntity',
            loader=projects_loader,
        ),
    ]
    id: int
    name: str
    project_id: int
    department_id: int


class ProjectEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(
            fk='id',
            name='documents',
            target=list[DocumentEntity],
            loader=project_documents_loader,
        ),
        Relationship(
            fk='department_id',
            name='department',
            target='DepartmentEntity',
            loader=departments_loader,
        ),
    ]
    id: int
    name: str
    department_id: int


class DepartmentEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(
            fk='id',
            name='projects',
            target=list[ProjectEntity],
            loader=department_projects_loader,
        )
    ]
    id: int
    name: str


class UserEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(
            fk='id',
            name='departments',
            target=list[DepartmentEntity],
            loader=user_departments_by_scope_loader,
        ),
        # Direct project access (independent of department hierarchy)
        Relationship(
            fk='id',
            name='projects',
            target=list[ProjectEntity],
            loader=user_projects_by_scope_loader,
        ),
        # Direct document access (independent of hierarchy)
        Relationship(
            fk='id',
            name='documents',
            target=list[DocumentEntity],
            loader=user_documents_by_scope_loader,
        ),
    ]
    id: int
    name: str


# ── Permission entities ──


class PermissionEntity(BaseModel, BaseEntity):
    __relationships__ = []
    id: int
    name: str
    action: str
    resource_type: str


class RolePermissionEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(
            fk='permission_id',
            name='permission',
            target=PermissionEntity,
            loader=permission_by_id_loader,
        ),
    ]
    id: int
    role_id: int
    permission_id: int
    resource_type: str | None = None
    resource_id: int | None = None
    effect: str = "allow"
    condition: str | None = None


class RoleEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(
            fk='id',
            name='role_permissions',
            target=list[RolePermissionEntity],
            loader=role_permission_rows_loader,
        ),
    ]
    id: int
    name: str
    description: str = ""


class UserRoleEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(
            fk='role_id',
            name='role',
            target=RoleEntity,
            loader=role_loader,
        ),
    ]
    id: int
    user_id: int
    role_id: int


class GroupRoleEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(
            fk='role_id',
            name='role',
            target=RoleEntity,
            loader=role_loader,
        ),
    ]
    id: int
    group_id: int
    role_id: int


class MailGroupEntity(BaseModel, BaseEntity):
    __relationships__ = []
    id: int
    name: str
    email: str


diagram = BaseEntity.get_diagram()


async def _scope_provider(context):
    """Adapter: extract user_id/action from Resolver context, compute scope."""
    if context is None:
        return {}
    user_id = context.get('user_id')
    if user_id is None:
        return {}
    from .scope import compute_user_scope
    action = context.get('action', 'read')
    return await compute_user_scope(user_id=user_id, action=action)


diagram.enable_scope(scope_provider=_scope_provider)
AutoLoad = diagram.create_auto_load()
config_global_resolver(diagram)
