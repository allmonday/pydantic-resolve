"""Task-related DTOs — UserSummary, TaskSummary."""
from typing import Annotated

from pydantic_resolve import AutoLoad, DefineSubset

from src.entities import TaskEntity, UserEntity


class UserSummary(DefineSubset):
    __subset__ = (UserEntity, ["id", "name"])


class TaskSummary(DefineSubset):
    """Task DTO — owner is auto-loaded from Task.owner relationship."""

    __subset__ = (TaskEntity, ["id", "title", "done"])
    owner_detail: Annotated[UserSummary | None, AutoLoad(origin="owner")] = None
