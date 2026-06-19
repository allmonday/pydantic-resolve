"""UseCase FastAPI Demo — FastAPI routes calling UseCaseService classmethods.

Demonstrates how the same UseCaseService classes used by MCP can be called
directly from FastAPI routes, showing that business logic lives in one
place and serves both HTTP API and MCP.

Routes are grouped by OpenAPI tags derived from Service.get_tag_name().

Run:
    uv run uvicorn demo.use_case.app:app --reload

Endpoints:
    GET /api/users                        — User list
    GET /api/tasks                        — Task list with auto-loaded owner
    GET /api/tasks/by-sprint/{sprint_id}  — Tasks filtered by sprint
    GET /api/tasks/{task_id}              — Single task by ID
    GET /api/sprints                      — Sprint list with derived fields
    GET /api/sprints/{sprint_id}          — Single sprint by ID
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from demo.use_case.database import init_db
from demo.use_case.services import SprintService, TaskService, UserService


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="UseCase FastAPI Demo",
    description="FastAPI routes calling UseCaseService classmethods",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "message": "UseCase FastAPI Demo",
        "endpoints": {
            "users": "/api/users",
            "tasks": "/api/tasks",
            "tasks_by_sprint": "/api/tasks/by-sprint/{sprint_id}",
            "task_detail": "/api/tasks/{task_id}",
            "sprints": "/api/sprints",
            "sprint_detail": "/api/sprints/{sprint_id}",
            "docs": "/docs — FastAPI Swagger UI",
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


@app.get("/api/tasks/by-sprint/{sprint_id}", tags=[TaskService.get_tag_name()])
async def get_tasks_by_sprint(sprint_id: int):
    """Get tasks for a specific sprint with auto-loaded owner."""
    return await TaskService.get_tasks_by_sprint(sprint_id=sprint_id)


@app.get("/api/tasks/{task_id}", tags=[TaskService.get_tag_name()])
async def get_task(task_id: int):
    """Get a single task by ID."""
    result = await TaskService.get_task(task_id=task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


# ──────────────────────────────────────────────────
# Sprint endpoints
# ──────────────────────────────────────────────────


@app.get("/api/sprints", tags=[SprintService.get_tag_name()])
async def get_sprints():
    """List all sprints with task counts and contributor names."""
    return await SprintService.list_sprints()


@app.get("/api/sprints/{sprint_id}", tags=[SprintService.get_tag_name()])
async def get_sprint(sprint_id: int):
    """Get a single sprint by ID with full details."""
    result = await SprintService.get_sprint(sprint_id=sprint_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Sprint not found")
    return result


if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.environ.get("PORT", 8007))
    uvicorn.run(app, host="0.0.0.0", port=port)
