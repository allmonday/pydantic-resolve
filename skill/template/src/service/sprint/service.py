"""Sprint UseCaseService — sprint management with task statistics."""
from pydantic_resolve import query
from pydantic_resolve.use_case import UseCaseService

from src.entities import MyResolver
from src.service.sprint.dtos import SprintSummary
from src.service.sprint.methods import (
    get_sprint as _get_sprint,
)
from src.service.sprint.methods import (
    list_sprints as _list_sprints,
)


class SprintService(UseCaseService):
    """Sprint management with task statistics."""

    @query
    async def list_sprints(cls) -> list[SprintSummary]:
        """Get all sprints with tasks and statistics."""
        sprints = await _list_sprints()
        dtos = [SprintSummary.model_validate(s) for s in sprints]
        return await MyResolver(enable_from_attribute_in_type_adapter=True).resolve(
            dtos
        )

    @query
    async def get_sprint(cls, sprint_id: int) -> SprintSummary | None:
        """Get a sprint by ID."""
        sprint = await _get_sprint(sprint_id=sprint_id)
        if sprint is None:
            return None
        dto = SprintSummary.model_validate(sprint)
        resolved = await MyResolver(
            enable_from_attribute_in_type_adapter=True
        ).resolve([dto])
        return resolved[0]
