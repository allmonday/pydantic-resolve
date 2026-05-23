"""Phase 3: REST router — calls UseCaseService methods."""
from fastapi import APIRouter, HTTPException

from src.service.sprint.service import SprintService
from src.service.task.service import TaskService

route = APIRouter(prefix="/api")


@route.get("/tasks", tags=[TaskService.get_tag_name()])
async def get_tasks():
    """List all tasks with auto-loaded owner."""
    return await TaskService.list_tasks()


@route.get("/tasks/by-sprint/{sprint_id}", tags=[TaskService.get_tag_name()])
async def get_tasks_by_sprint(sprint_id: int):
    """Get tasks for a specific sprint with auto-loaded owner."""
    return await TaskService.get_tasks_by_sprint(sprint_id=sprint_id)


@route.get("/tasks/{task_id}", tags=[TaskService.get_tag_name()])
async def get_task(task_id: int):
    """Get a single task by ID."""
    result = await TaskService.get_task(task_id=task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@route.get("/sprints", tags=[SprintService.get_tag_name()])
async def get_sprints():
    """List all sprints with task counts and contributor names."""
    return await SprintService.list_sprints()


@route.get("/sprints/{sprint_id}", tags=[SprintService.get_tag_name()])
async def get_sprint(sprint_id: int):
    """Get a single sprint by ID with full details."""
    result = await SprintService.get_sprint(sprint_id=sprint_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Sprint not found")
    return result
