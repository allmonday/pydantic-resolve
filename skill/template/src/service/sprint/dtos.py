"""Sprint-related DTOs — SprintSummary with derived fields."""
from typing import Annotated

from pydantic_resolve import AutoLoad, DefineSubset

from src.entities import SprintEntity, TaskEntity


class SprintSummary(DefineSubset):
    """Sprint DTO with derived fields computed after tasks are loaded."""

    __subset__ = (SprintEntity, ["id", "name"])
    task_list: Annotated[list[TaskEntity], AutoLoad(origin="tasks")] = []
    task_count: int = 0
    contributor_names: list[str] = []

    def post_task_count(self):
        return len(self.task_list)

    def post_contributor_names(self):
        return sorted({t.owner.name for t in self.task_list if t.owner})
