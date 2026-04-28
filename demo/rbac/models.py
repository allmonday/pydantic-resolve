"""SQLAlchemy ORM models for RBAC/ABAC demo."""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    email: Mapped[str] = mapped_column(String(256))
    level: Mapped[int] = mapped_column(Integer, default=1)


class UserDepartment(Base):
    """M:N intermediate table: user can belong to multiple departments."""
    __tablename__ = "user_departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    department_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.id"))

    __table_args__ = (UniqueConstraint("user_id", "department_id"),)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(32))  # read, write, delete, admin
    resource_type: Mapped[str] = mapped_column(String(64))  # department, project, document, *


# ── Resource tables (three separate tables) ──


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256))
    owner_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visibility: Mapped[str] = mapped_column(String(32), default="internal")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256))
    department_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.id"))
    owner_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visibility: Mapped[str] = mapped_column(String(32), default="internal")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256))
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"))
    department_id: Mapped[int] = mapped_column(Integer)
    owner_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visibility: Mapped[str] = mapped_column(String(32), default="internal")


# ── Assignment tables ──


class UserRole(Base):
    __tablename__ = "user_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"))
    granted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "role_id"),)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"))
    permission_id: Mapped[int] = mapped_column(Integer, ForeignKey("permissions.id"))
    # Polymorphic resource reference: (resource_type, resource_id) together
    # identify the target resource across department/project/document tables.
    # Both NULL means global permission (applies to all resources).
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    effect: Mapped[str] = mapped_column(String(8), default="allow")  # allow, deny
    # Named condition reference — actual condition logic is in condition.py
    condition: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (UniqueConstraint("role_id", "permission_id", "resource_type", "resource_id"),)


class MailGroup(Base):
    """Mail distribution group from external system."""
    __tablename__ = "mail_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    email: Mapped[str] = mapped_column(String(256))


class GroupRole(Base):
    """Mail group -> role assignment, like UserRole but for groups."""
    __tablename__ = "group_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("mail_groups.id"))
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"))
