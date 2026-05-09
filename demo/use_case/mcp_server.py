"""UseCase MCP server for Sprint/Task/User management.

Demonstrates pydantic-resolve patterns:
- SQLAlchemy ORM + build_relationship for auto-generated loaders
- ErDiagram + AutoLoad for declarative relationship loading
- DefineSubset for progressive field complexity
- UseCaseService for business services exposed via MCP
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from pydantic_resolve import ErDiagram, DefineSubset, config_resolver, AutoLoad, query
from pydantic_resolve.integration.mapping import Mapping
from pydantic_resolve.integration.sqlalchemy import build_relationship
from pydantic_resolve.use_case import UseCaseService, UseCaseAppConfig, create_use_case_mcp_server

from demo.use_case.database import (
    UserOrm,
    TaskOrm,
    SprintOrm,
    session_factory,
    init_db,
)


# ──────────────────────────────────────────────────
# Entity DTOs (from_attributes=True for ORM conversion)
# ──────────────────────────────────────────────────


class UserEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str


class TaskEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    owner_id: int
    sprint_id: int


class SprintEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


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
    __subset__ = (UserEntity, ["id", "name"])


class TaskSummary(DefineSubset):
    __subset__ = (TaskEntity, ["id", "title"])
    owner_detail: Annotated[UserSummary | None, AutoLoad(origin="owner")] = None


class SprintSummary(DefineSubset):
    __subset__ = (SprintEntity, ["id", "name"])
    task_list: Annotated[list[TaskEntity], AutoLoad(origin="tasks")] = []
    task_count: int = 0
    contributor_names: list[str] = []

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


# ──────────────────────────────────────────────────
# MCP Server entry point
# ──────────────────────────────────────────────────


def create_server():
    """Create the UseCase MCP server."""
    return create_use_case_mcp_server(
        apps=[
            UseCaseAppConfig(
                name="sprint",
                description="Sprint management with tasks and users",
                services=[UserService, TaskService, SprintService],
            ),
        ],
        name="Sprint UseCase MCP Demo",
    )


def main() -> None:
    """Run the MCP server (stdio or HTTP mode)."""
    import asyncio

    import uvicorn

    asyncio.run(init_db())
    mcp = create_server()

    mcp_app = mcp.http_app(transport="streamable-http", stateless_http=True)
    uvicorn.run(mcp_app, host="0.0.0.0", port=8006)


if __name__ == "__main__":
    main()
