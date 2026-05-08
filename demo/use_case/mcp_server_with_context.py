"""Demo UseCase MCP server with context extraction from HTTP headers.

This example demonstrates how to use ``Annotated[type, FromContext()]`` to
mark method parameters that should be injected from the MCP context_extractor,
while keeping the method signature identical for FastAPI usage.

Flow:
    HTTP Request (Authorization: Bearer <user_id>)
      -> FastMCP Context (ctx)
        -> context_extractor(ctx) -> {"user_id": <user_id>}
          -> call_use_case merges context into kwargs
            -> TaskService.get_my_tasks(user_id=<user_id>)

Usage:
    # Run with streamable-http transport
    uv run python -m demo.use_case.mcp_server_with_context

    # Test with curl:
    # 1. Get tasks for user_id=1 (Alice):
    #    curl -X POST http://localhost:8006/mcp/ \
    #      -H "Authorization: Bearer 1" \
    #      -H "Content-Type: application/json" \
    #      -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"call_use_case","arguments":{"app_name":"sprint","service_name":"TaskService","method_name":"get_my_tasks","params":"{}"}},"id":1}'

    # 2. List all tasks (no context needed):
    #    curl -X POST http://localhost:8006/mcp/ \
    #      -H "Content-Type: application/json" \
    #      -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"call_use_case","arguments":{"app_name":"sprint","service_name":"TaskService","method_name":"list_tasks","params":"{}"}},"id":2}'
"""

from typing import Annotated

from fastmcp.server.context import Context
from fastmcp.server.dependencies import get_http_headers
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from pydantic_resolve import ErDiagram, DefineSubset, config_resolver
from pydantic_resolve.integration.mapping import Mapping
from pydantic_resolve.integration.sqlalchemy import build_relationship
from pydantic_resolve.use_case import (
    FromContext,
    UseCaseAppConfig,
    UseCaseService,
    create_use_case_mcp_server,
)

from demo.use_case.database import (
    TaskOrm,
    SprintOrm,
    UserOrm,
    init_db,
    session_factory,
)


# ──────────────────────────────────────────────────
# Entity DTOs
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
AutoLoad = diagram.create_auto_load()
MyResolver = config_resolver("UseCaseContextDemoResolver", er_diagram=diagram)


# ──────────────────────────────────────────────────
# DefineSubset DTOs
# ──────────────────────────────────────────────────


class UserSummary(DefineSubset):
    __subset__ = (UserEntity, ["id", "name"])


class TaskSummary(DefineSubset):
    __subset__ = (TaskEntity, ["id", "title"])
    owner_detail: Annotated[UserSummary | None, AutoLoad(origin="owner")] = None


# ──────────────────────────────────────────────────
# Context extractor
# ──────────────────────────────────────────────────


def extract_user_context(ctx: Context) -> dict:
    """Extract user_id from Authorization: Bearer <user_id> header.

    In production, you would decode a JWT token here and extract
    claims like user_id, roles, permissions, etc.

    For this demo, the token IS the user_id (integer).
    """
    # NOTE: get_http_headers() strips 'authorization' by default.
    # Must pass include={"authorization"} to receive it.
    headers = get_http_headers(include={"authorization"})
    auth = headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        try:
            return {"user_id": int(token)}
        except ValueError:
            pass
    return {}


# ──────────────────────────────────────────────────
# UseCaseService classes
# ──────────────────────────────────────────────────


class UserService(UseCaseService):
    """User management service."""

    @classmethod
    async def list_users(cls) -> list[UserSummary]:
        """Get all users."""
        async with session_factory() as session:
            result = await session.execute(select(UserOrm).order_by(UserOrm.id))
            rows = result.scalars().all()
        dtos = [UserSummary.model_validate(r) for r in rows]
        return await MyResolver(enable_from_attribute_in_type_adapter=True).resolve(dtos)


class TaskService(UseCaseService):
    """Task management service with context-aware queries."""

    @classmethod
    async def list_tasks(cls) -> list[TaskSummary]:
        """Get all tasks with auto-loaded owner."""
        async with session_factory() as session:
            result = await session.execute(select(TaskOrm).order_by(TaskOrm.id))
            rows = result.scalars().all()
        dtos = [TaskSummary.model_validate(r) for r in rows]
        return await MyResolver(enable_from_attribute_in_type_adapter=True).resolve(dtos)

    @classmethod
    async def get_my_tasks(cls, user_id: Annotated[int, FromContext()]) -> list[TaskSummary]:
        """Get tasks owned by the authenticated user.

        user_id is injected from context_extractor (MCP) or passed
        directly (FastAPI). The method signature is identical in both.
        """
        async with session_factory() as session:
            result = await session.execute(
                select(TaskOrm)
                .where(TaskOrm.owner_id == user_id)
                .order_by(TaskOrm.id)
            )
            rows = result.scalars().all()
        dtos = [TaskSummary.model_validate(r) for r in rows]
        return await MyResolver(enable_from_attribute_in_type_adapter=True).resolve(dtos)


# ──────────────────────────────────────────────────
# MCP Server entry point
# ──────────────────────────────────────────────────


def create_server():
    """Create the UseCase MCP server with context extraction."""
    return create_use_case_mcp_server(
        apps=[
            UseCaseAppConfig(
                name="sprint",
                description="Sprint management with context-aware task queries. "
                "Use Authorization: Bearer <user_id> header to authenticate. "
                "The get_my_tasks method returns only the authenticated user's tasks.",
                services=[UserService, TaskService],
                context_extractor=extract_user_context,
            ),
        ],
        name="Sprint UseCase MCP Demo (with Context)",
    )


def main() -> None:
    """Run the MCP server (HTTP mode)."""
    import asyncio

    import uvicorn

    asyncio.run(init_db())
    mcp = create_server()

    mcp_app = mcp.http_app(transport="streamable-http", stateless_http=True)
    uvicorn.run(mcp_app, host="0.0.0.0", port=8006)


if __name__ == "__main__":
    main()
