"""Context-aware UseCase services for the FastAPI/MCP dual-mode demo.

Demonstrates the ``Annotated[type, FromContext()]`` pattern where a
single method (e.g. ``TaskService.get_my_tasks(user_id=...)``) can be
called from either:

- **FastAPI**: ``user_id`` comes from ``Depends(get_current_user)``
- **MCP**:     ``user_id`` comes from ``context_extractor`` via
               ``FromContext()``

The method signature is identical in both — only the parameter source
differs.

Used by ``demo/use_case/app_with_context.py``. Entity / subset /
resolver definitions are shared with ``services.py`` so the underlying
ORM mapping stays in sync.
"""

from typing import Annotated

from fastmcp.server.context import Context
from fastmcp.server.dependencies import get_http_headers
from pydantic import Field
from sqlalchemy import select

from pydantic_resolve import AutoLoad, DefineSubset, FromContext, query
from pydantic_resolve.use_case import UseCaseService

from demo.use_case.database import TaskOrm, UserOrm, session_factory
from demo.use_case.services import (
    MyResolver,
    TaskEntity,
    UserSummary,
)


class TaskSummary(DefineSubset):
    """Task view with auto-loaded owner. Mirrors ``services.TaskSummary``;

    re-declared here so ``services_context`` stays a self-contained
    import target for the context-aware demo.
    """

    __subset__ = (TaskEntity, ["id", "title", "status"])
    owner_detail: Annotated[
        UserSummary | None,
        AutoLoad(origin="owner"),
    ] = Field(
        default=None,
        description="Auto-loaded owner of this task.",
    )


def extract_user_context(ctx: Context) -> dict:
    """Extract ``user_id`` from ``Authorization: Bearer <user_id>`` header.

    In production you'd decode a JWT and extract user_id / roles / etc.
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


class UserService(UseCaseService):
    """User management service (context variant — list_users only)."""

    @query
    async def list_users(cls) -> list[UserSummary]:
        """Get all users."""
        async with session_factory() as session:
            result = await session.execute(select(UserOrm).order_by(UserOrm.id))
            rows = result.scalars().all()
        dtos = [UserSummary.model_validate(r) for r in rows]
        return await MyResolver(enable_from_attribute_in_type_adapter=True).resolve(dtos)


class TaskService(UseCaseService):
    """Task management service with context-aware queries.

    ``get_my_tasks`` accepts ``user_id`` via ``FromContext()`` — when
    called via MCP, the value comes from ``extract_user_context``;
    when called directly (e.g. from FastAPI), the caller passes it.
    """

    @query
    async def list_tasks(cls) -> list[TaskSummary]:
        """Get all tasks with auto-loaded owner."""
        async with session_factory() as session:
            result = await session.execute(select(TaskOrm).order_by(TaskOrm.id))
            rows = result.scalars().all()
        dtos = [TaskSummary.model_validate(r) for r in rows]
        return await MyResolver(enable_from_attribute_in_type_adapter=True).resolve(dtos)

    @query
    async def get_my_tasks(cls, user_id: Annotated[int, FromContext()]) -> list[TaskSummary]:
        """Get tasks owned by the authenticated user.

        ``user_id`` is injected from ``context_extractor`` (MCP) or
        passed directly (FastAPI). The method signature is identical
        in both.
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
