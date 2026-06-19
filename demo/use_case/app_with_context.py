"""UseCase FastAPI Demo with context — shows context-aware services called from FastAPI.

This demo mirrors ``app.py`` but uses the context-aware services from
``services_context``. It demonstrates that a UseCaseService method like
``TaskService.get_my_tasks(user_id=...)`` works identically in:

- **FastAPI**: ``user_id`` comes from ``Depends(get_current_user)``
- **MCP**:     ``user_id`` comes from ``context_extractor`` via ``FromContext()``

The method signature is the same; only the parameter source differs.

Run:
    uv run uvicorn demo.use_case.app_with_context:app --reload

Endpoints:
    GET /api/users           — User list
    GET /api/tasks           — Task list with auto-loaded owner
    GET /api/tasks/my-tasks  — Tasks owned by the authenticated user (context demo)
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from demo.use_case.database import init_db
from demo.use_case.services_context import TaskService, UserService


# ──────────────────────────────────────────────────
# Auth dependency (simplified for demo)
# ──────────────────────────────────────────────────


async def get_current_user(user_id: int = 1) -> int:
    """Return the authenticated user's ID.

    In production this would decode a JWT from the Authorization header.
    For this demo, user_id defaults to 1 (Alice) but can be overridden
    via query parameter for testing: ``/api/tasks/my-tasks?user_id=2``.
    """
    return user_id


# ──────────────────────────────────────────────────
# FastAPI app
# ──────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="UseCase FastAPI Demo (with Context)",
    description=(
        "FastAPI routes calling the same UseCaseService methods as MCP. "
        "The get_my_tasks endpoint shows user_id passed via Depends, "
        "while MCP passes it via context_extractor + FromContext()."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    return {
        "message": "UseCase FastAPI Demo (with Context)",
        "endpoints": {
            "users": "/api/users",
            "tasks": "/api/tasks",
            "my_tasks": "/api/tasks/my-tasks?user_id=1 (context demo)",
            "docs": "/docs",
        },
    }


# ──────────────────────────────────────────────────
# User endpoints
# ──────────────────────────────────────────────────


@app.get("/api/users", tags=[UserService.get_tag_name()])
async def get_users():
    """List all users."""
    return await UserService.list_users()


# ──────────────────────────────────────────────────
# Task endpoints
# ──────────────────────────────────────────────────


@app.get("/api/tasks", tags=[TaskService.get_tag_name()])
async def get_tasks():
    """List all tasks with auto-loaded owner."""
    return await TaskService.list_tasks()


@app.get("/api/tasks/my-tasks", tags=[TaskService.get_tag_name()])
async def get_my_tasks(user_id: int = Depends(get_current_user)):
    """Get tasks owned by the authenticated user.

    This calls the same ``TaskService.get_my_tasks`` method that MCP calls,
    but ``user_id`` comes from FastAPI's ``Depends`` instead of ``FromContext()``.

    The method signature is identical in both scenarios:
        ``TaskService.get_my_tasks(user_id=<int>)``
    """
    return await TaskService.get_my_tasks(user_id=user_id)


if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.environ.get("PORT", 8008))
    uvicorn.run(app, host="0.0.0.0", port=port)
