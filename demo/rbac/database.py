"""SQLite async database setup and seed data for RBAC/ABAC demo."""

import os
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models import (
    Base,
    Department,
    Document,
    GroupRole,
    MailGroup,
    Permission,
    Project,
    Role,
    RolePermission,
    User,
    UserDepartment,
    UserRole,
)

DB_PATH = os.path.join(os.path.dirname(__file__), "rbac_demo.db")
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

engine = None
_async_session_factory = None


def get_engine():
    global engine
    if engine is None:
        engine = create_async_engine(DB_URL, echo=False)
    return engine


def get_session_factory():
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _async_session_factory


@asynccontextmanager
async def session_factory():
    """Async context manager that yields a database session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def init_db():
    """Create tables and insert seed data."""
    # Remove old DB file
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    eng = get_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = get_session_factory()
    async with factory() as session:
        await _seed_data(session)
        await session.commit()


async def _seed_data(session: AsyncSession):
    """Insert comprehensive seed data demonstrating RBAC + ABAC scenarios."""

    # ── Users (2 departments: Engineering=1, Marketing=2) ──
    users = [
        User(id=1, name="Alice", email="alice@example.com", level=3),
        User(id=2, name="Bob", email="bob@example.com", level=2),
        User(id=3, name="Charlie", email="charlie@example.com", level=2),
        User(id=4, name="Diana", email="diana@example.com", level=1),
        User(id=5, name="Eve", email="eve@example.com", level=1),
    ]
    session.add_all(users)

    # ── User-Department assignments (M:N) ──
    # Alice spans both departments (cross-dept admin)
    user_departments = [
        UserDepartment(id=1, user_id=1, department_id=1),  # Alice → Engineering
        UserDepartment(id=2, user_id=1, department_id=2),  # Alice → Marketing
        UserDepartment(id=3, user_id=2, department_id=1),  # Bob → Engineering
        UserDepartment(id=4, user_id=3, department_id=2),  # Charlie → Marketing
        UserDepartment(id=5, user_id=4, department_id=2),  # Diana → Marketing
        UserDepartment(id=6, user_id=5, department_id=1),  # Eve → Engineering
    ]
    session.add_all(user_departments)

    # ── Roles ──
    roles = [
        Role(id=1, name="admin", description="Full access to everything"),
        Role(id=2, name="manager", description="Manage resources in own department"),
        Role(id=3, name="viewer", description="Read public and internal resources"),
        Role(id=4, name="restricted_viewer", description="Can only read specific department resources"),
    ]
    session.add_all(roles)

    # ── User-Role assignments ──
    user_roles = [
        UserRole(id=1, user_id=1, role_id=1),  # Alice is admin
        UserRole(id=2, user_id=1, role_id=2),  # Alice is also manager
        UserRole(id=3, user_id=2, role_id=2),  # Bob is manager
        UserRole(id=4, user_id=3, role_id=2),  # Charlie is manager
        UserRole(id=5, user_id=4, role_id=3),  # Diana is viewer
        UserRole(id=6, user_id=5, role_id=4),  # Eve is restricted_viewer
    ]
    session.add_all(user_roles)

    # ── Departments ──
    departments = [
        Department(id=1, name="Engineering", owner_id=1, visibility="internal"),
        Department(id=2, name="Marketing", owner_id=3, visibility="internal"),
    ]
    session.add_all(departments)

    # ── Projects ──
    #
    #  Engineering (dept=1)
    #  ├── Project Alpha  (owner=Bob, internal)
    #  └── Project Beta   (owner=Alice, confidential)
    #
    #  Marketing (dept=2)
    #  └── Campaign X     (owner=Charlie, internal)
    #
    projects = [
        Project(id=1, name="Project Alpha", department_id=1, owner_id=2, visibility="internal"),
        Project(id=2, name="Project Beta", department_id=1, owner_id=1, visibility="confidential"),
        Project(id=3, name="Campaign X", department_id=2, owner_id=3, visibility="internal"),
    ]
    session.add_all(projects)

    # ── Documents ──
    #
    #  Project Alpha (project=1, dept=1)
    #  ├── Design Doc     (owner=Bob, internal)
    #  └── API Doc        (owner=Alice, public)
    #
    #  Campaign X (project=3, dept=2)
    #  ├── Campaign Brief (owner=Charlie, internal)
    #  └── Budget Plan    (owner=Charlie, confidential)
    #
    documents = [
        Document(id=1, name="Design Doc", project_id=1, department_id=1, owner_id=2, visibility="internal"),
        Document(id=2, name="API Doc", project_id=1, department_id=1, owner_id=1, visibility="public"),
        Document(id=3, name="Campaign Brief", project_id=3, department_id=2, owner_id=3, visibility="internal"),
        Document(id=4, name="Budget Plan", project_id=3, department_id=2, owner_id=3, visibility="confidential"),
    ]
    session.add_all(documents)

    # ── Permissions ──
    permissions = [
        # Admin: full access
        Permission(id=1, name="admin_all", action="admin", resource_type="*"),
        Permission(id=2, name="delete_any", action="delete", resource_type="*"),
        # Manager: manage own department
        Permission(id=3, name="write_dept", action="write", resource_type="*"),
        Permission(id=4, name="read_dept", action="read", resource_type="*"),
        # Viewer: read public/internal
        Permission(id=5, name="read_public", action="read", resource_type="*"),
        # Viewer: export documents only (resource_type scoped)
        Permission(id=6, name="export_doc", action="export", resource_type="document"),
    ]
    session.add_all(permissions)

    # ── Role-Permissions (with named conditions) ──
    # resource_type=NULL + resource_id=NULL means global permission.
    # condition references a named condition defined in condition.py.
    role_permissions = [
        # Admin: no conditions, full access
        RolePermission(
            id=1, role_id=1, permission_id=1,
            resource_type=None, resource_id=None,
            effect="allow", condition=None,
        ),
        RolePermission(
            id=2, role_id=1, permission_id=2,
            resource_type=None, resource_id=None,
            effect="allow", condition=None,
        ),

        # Manager: write in own department, non-confidential only
        RolePermission(
            id=3, role_id=2, permission_id=3,
            resource_type=None, resource_id=None,
            effect="allow", condition="same_dept_non_confidential",
        ),
        # Manager: read in own department (including confidential)
        RolePermission(
            id=4, role_id=2, permission_id=4,
            resource_type=None, resource_id=None,
            effect="allow", condition="same_dept",
        ),

        # Viewer: read public and internal resources only
        RolePermission(
            id=5, role_id=3, permission_id=5,
            resource_type=None, resource_id=None,
            effect="allow", condition="public_internal_only",
        ),
        # Viewer: export documents only (Permission.resource_type="document")
        RolePermission(
            id=6, role_id=3, permission_id=6,
            resource_type=None, resource_id=None,
            effect="allow", condition=None,
        ),

        # Restricted viewer: read specific projects only (resource-scoped)
        RolePermission(
            id=7, role_id=4, permission_id=4,  # read_dept
            resource_type="project", resource_id=1,  # Project Alpha only
            effect="allow", condition=None,
        ),
    ]
    session.add_all(role_permissions)

    # ── Mail groups (distribution lists from external directory) ──
    mail_groups = [
        MailGroup(id=1, name="engineering-all", email="eng-all@acme.com"),
        MailGroup(id=2, name="marketing-all", email="mkt-all@acme.com"),
        MailGroup(id=3, name="eng-leads", email="eng-leads@acme.com"),
    ]
    session.add_all(mail_groups)

    # ── Group-Role assignments ──
    group_roles = [
        GroupRole(id=1, group_id=1, role_id=2),  # engineering-all → manager
        GroupRole(id=2, group_id=2, role_id=3),  # marketing-all → viewer
        GroupRole(id=3, group_id=3, role_id=1),  # eng-leads → admin
    ]
    session.add_all(group_roles)


async def cleanup_db():
    """Remove the database file."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
