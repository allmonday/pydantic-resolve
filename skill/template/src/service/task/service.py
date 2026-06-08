"""Task UseCaseService — task management with auto-loaded owner."""
from pydantic_resolve import query
from pydantic_resolve.use_case import UseCaseService

from src.entities import MyResolver
from src.service.task.dtos import TaskSummary
from src.service.task.methods import (
    get_task as _get_task,
)
from src.service.task.methods import (
    get_tasks_by_sprint as _get_tasks_by_sprint,
)
from src.service.task.methods import (
    list_tasks as _list_tasks,
)


class TaskService(UseCaseService):
    """Task management with auto-loaded owner."""

    @query
    async def list_tasks(cls) -> list[TaskSummary]:
        """Get all tasks with auto-loaded owner."""
        tasks = await _list_tasks()
        dtos = [TaskSummary.model_validate(t) for t in tasks]
        return await MyResolver(enable_from_attribute_in_type_adapter=True).resolve(
            dtos
        )

    @query
    async def get_tasks_by_sprint(cls, sprint_id: int) -> list[TaskSummary]:
        """Get tasks filtered by sprint ID."""
        tasks = await _get_tasks_by_sprint(sprint_id=sprint_id)
        dtos = [TaskSummary.model_validate(t) for t in tasks]
        return await MyResolver(enable_from_attribute_in_type_adapter=True).resolve(
            dtos
        )

    @query
    async def get_task(cls, task_id: int) -> TaskSummary | None:
        """Get a task by ID."""
        task = await _get_task(task_id=task_id)
        if task is None:
            return None
        dto = TaskSummary.model_validate(task)
        resolved = await MyResolver(
            enable_from_attribute_in_type_adapter=True
        ).resolve([dto])
        return resolved[0]
