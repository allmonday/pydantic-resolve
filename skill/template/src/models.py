"""Phase 1: SQLAlchemy ORM models (pure fields + relationship, no business methods).

Entity graph:
    Sprint ──1:N──→ Task ──N:1──→ User
"""
from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserOrm(Base):
    """系统用户，可以是任务的创建者或负责人。"""

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()

    # ORM relationships (noload: use explicit queries or Resolver DataLoader)
    tasks: Mapped[list["TaskOrm"]] = relationship(
        back_populates="owner",
        lazy="noload",
    )


class SprintOrm(Base):
    """迭代周期，包含一批待完成的任务。"""

    __tablename__ = "sprint"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()

    # ORM relationships (noload)
    tasks: Mapped[list["TaskOrm"]] = relationship(
        back_populates="sprint",
        lazy="noload",
        order_by="TaskOrm.id",
    )


class TaskOrm(Base):
    """具体的工作项，属于某个 Sprint，由某个 User 负责。"""

    __tablename__ = "task"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column()
    done: Mapped[bool] = mapped_column(default=False)

    sprint_id: Mapped[int] = mapped_column(ForeignKey("sprint.id"))
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user.id"), default=None
    )

    # ORM relationships (noload)
    sprint: Mapped["SprintOrm"] = relationship(back_populates="tasks", lazy="noload")
    owner: Mapped[Optional["UserOrm"]] = relationship(lazy="noload")
