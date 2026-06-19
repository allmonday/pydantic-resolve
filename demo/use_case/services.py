"""Shared UseCase services for the Sprint/Task/User demo.

Consumed by the GraphQL compose MCP demo (``mcp_server_compose.py``)
and the FastAPI compose demo (``app_compose.py``).
"""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from pydantic_resolve import ErDiagram, DefineSubset, config_resolver, AutoLoad, query
from pydantic_resolve.integration.mapping import Mapping
from pydantic_resolve.integration.sqlalchemy import build_relationship
from pydantic_resolve.use_case import UseCaseService

from demo.use_case.database import (
    UserOrm,
    TaskOrm,
    SprintOrm,
    session_factory,
)


# ──────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────


class TaskStatus(str, Enum):
    """Lifecycle status of a task.

    Also doubles as the ``str`` value stored in the ORM, so it
    serializes cleanly to JSON without an explicit value mapping.
    """

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


# ──────────────────────────────────────────────────
# Entity DTOs (from_attributes=True for ORM conversion)
# ──────────────────────────────────────────────────


class UserEntity(BaseModel):
    """A user account. Owner of tasks and member of sprints."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Primary key.")
    name: str = Field(description="Display name shown in UI.")
    email: str = Field(description="Login email, unique per user.")


class TaskEntity(BaseModel):
    """A unit of work belonging to a sprint and owned by a user."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Primary key.")
    title: str = Field(description="Short summary of the work.")
    owner_id: int = Field(description="FK to ``UserEntity.id``.")
    sprint_id: int = Field(description="FK to ``SprintEntity.id``.")
    status: TaskStatus = Field(
        default=TaskStatus.TODO,
        description="Current lifecycle status. See ``TaskStatus``.",
    )


class SprintEntity(BaseModel):
    """A time-boxed iteration containing a set of tasks."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Primary key.")
    name: str = Field(description="Sprint name, e.g. ``Sprint 2026-W26``.")


# ──────────────────────────────────────────────────
# ER Diagram + build_relationship + AutoLoad
# ──────────────────────────────────────────────────

entities = build_relationship(
    mappings=[
        Mapping(entity=UserEntity, orm=UserOrm),
        Mapping(entity=TaskEntity, orm=TaskOrm),
        Mapping(entity=SprintEntity, orm=SprintOrm),
    ],
    session_factory=session_factory,
)

diagram = ErDiagram(entities=[]).add_relationship(entities)
MyResolver = config_resolver("UseCaseDemoResolver", er_diagram=diagram)


# ──────────────────────────────────────────────────
# DefineSubset DTOs — progressive complexity
# ──────────────────────────────────────────────────


class UserSummary(DefineSubset):
    # NOTE: DefineSubset's metaclass strips class docstrings, so the
    # SDL output for subset DTOs shows no type-level description even
    # when one is written here. Field-level descriptions (via Field)
    # still come through. Entity classes (UserEntity etc.) keep their
    # docstrings normally.
    """Lightweight user view used when embedding owner info inside tasks."""

    __subset__ = (UserEntity, ["id", "name"])


class TaskSummary(DefineSubset):
    """Task view with auto-loaded owner. Returned by all TaskService methods."""

    __subset__ = (TaskEntity, ["id", "title", "status"])
    owner_detail: Annotated[
        UserSummary | None,
        AutoLoad(origin="owner"),
    ] = Field(
        default=None,
        description="Auto-loaded owner of this task.",
    )


class SprintSummary(DefineSubset):
    """Sprint view with task list + computed statistics."""

    __subset__ = (SprintEntity, ["id", "name"])
    task_list: Annotated[
        list[TaskEntity],
        AutoLoad(origin="tasks"),
    ] = Field(
        default_factory=list,
        description="All tasks assigned to this sprint.",
    )
    task_count: int = Field(
        default=0,
        description="Number of tasks in this sprint (computed via ``post_task_count``).",
    )
    contributor_names: list[str] = Field(
        default_factory=list,
        description="Distinct owner names across this sprint's tasks.",
    )

    def post_task_count(self):
        return len(self.task_list)

    def post_contributor_names(self):
        return []


# ──────────────────────────────────────────────────
# UseCaseService classes
# ──────────────────────────────────────────────────


class UserService(UseCaseService):
    """User management service."""

    @query
    async def list_users(cls) -> list[UserSummary]:
        """Get all users."""
        async with session_factory() as session:
            result = await session.execute(select(UserOrm).order_by(UserOrm.id))
            rows = result.scalars().all()
        dtos = [UserSummary.model_validate(r) for r in rows]
        return await MyResolver(enable_from_attribute_in_type_adapter=True).resolve(dtos)

    @query
    async def get_user(cls, user_id: int) -> UserSummary | None:
        """Get a user by ID."""
        async with session_factory() as session:
            result = await session.execute(
                select(UserOrm).where(UserOrm.id == user_id)
            )
            row = result.scalar_one_or_none()
        if row is None:
            return None
        dto = UserSummary.model_validate(row)
        resolved = await MyResolver(enable_from_attribute_in_type_adapter=True).resolve([dto])
        return resolved[0]


class TaskService(UseCaseService):
    """Task management service."""

    @query
    async def list_tasks(cls) -> list[TaskSummary]:
        """Get all tasks with auto-loaded owner."""
        async with session_factory() as session:
            result = await session.execute(select(TaskOrm).order_by(TaskOrm.id))
            rows = result.scalars().all()
        dtos = [TaskSummary.model_validate(r) for r in rows]
        return await MyResolver(enable_from_attribute_in_type_adapter=True).resolve(dtos)

    @query
    async def get_tasks_by_sprint(cls, sprint_id: int) -> list[TaskSummary]:
        """Get tasks filtered by sprint ID."""
        async with session_factory() as session:
            result = await session.execute(
                select(TaskOrm)
                .where(TaskOrm.sprint_id == sprint_id)
                .order_by(TaskOrm.id)
            )
            rows = result.scalars().all()
        dtos = [TaskSummary.model_validate(r) for r in rows]
        return await MyResolver(enable_from_attribute_in_type_adapter=True).resolve(dtos)

    @query
    async def get_task(cls, task_id: int) -> TaskSummary | None:
        """Get a task by ID."""
        async with session_factory() as session:
            result = await session.execute(
                select(TaskOrm).where(TaskOrm.id == task_id)
            )
            row = result.scalar_one_or_none()
        if row is None:
            return None
        dto = TaskSummary.model_validate(row)
        resolved = await MyResolver(enable_from_attribute_in_type_adapter=True).resolve([dto])
        return resolved[0]


class SprintService(UseCaseService):
    """Sprint management service with task statistics."""

    @query
    async def list_sprints(cls) -> list[SprintSummary]:
        """Get all sprints with tasks and statistics."""
        async with session_factory() as session:
            result = await session.execute(select(SprintOrm).order_by(SprintOrm.id))
            rows = result.scalars().all()
        dtos = [SprintSummary.model_validate(r) for r in rows]
        return await MyResolver(enable_from_attribute_in_type_adapter=True).resolve(dtos)

    @query
    async def get_sprint(cls, sprint_id: int) -> SprintSummary | None:
        """Get a sprint by ID with tasks and statistics."""
        async with session_factory() as session:
            result = await session.execute(
                select(SprintOrm).where(SprintOrm.id == sprint_id)
            )
            row = result.scalar_one_or_none()
        if row is None:
            return None
        dto = SprintSummary.model_validate(row)
        resolved = await MyResolver(enable_from_attribute_in_type_adapter=True).resolve([dto])
        return resolved[0]
