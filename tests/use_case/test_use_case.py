"""Tests for the UseCase module — UseCaseService.

MCP server tests live in ``test_compose_mcp.py``.
"""

from __future__ import annotations

from pydantic import BaseModel

from pydantic_resolve import query, mutation
from pydantic_resolve.use_case.business import UseCaseService

# ──────────────────────────────────────────────────
# Test DTOs
# ──────────────────────────────────────────────────


class UserDTO(BaseModel):
    id: int
    name: str


class TaskDTO(BaseModel):
    id: int
    title: str
    owner: UserDTO | None = None


class CreateUserDTO(BaseModel):
    name: str
    email: str


# ──────────────────────────────────────────────────
# Test Services
# ──────────────────────────────────────────────────


class UserService(UseCaseService):
    """User management service."""

    @query
    async def list_users(cls) -> list[UserDTO]:
        """Get all users."""
        return [UserDTO(id=1, name="Alice"), UserDTO(id=2, name="Bob")]

    @query
    async def get_user(cls, user_id: int) -> UserDTO | None:
        """Get a user by ID."""
        if user_id == 1:
            return UserDTO(id=1, name="Alice")
        return None

    @mutation
    async def create_user(cls, name: str, email: str) -> UserDTO:
        """Create a new user."""
        return UserDTO(id=99, name=name)

    @mutation
    async def register(cls, data: CreateUserDTO) -> UserDTO:
        """Register a new user."""
        return UserDTO(id=99, name=data.name)


class TaskService(UseCaseService):
    """Task management service."""

    @query
    async def list_tasks(cls) -> list[TaskDTO]:
        """Get all tasks."""
        return [
            TaskDTO(id=1, title="Task 1", owner=UserDTO(id=1, name="Alice")),
        ]

    @classmethod
    async def _internal_helper(cls) -> str:
        """This should NOT be exposed (no @query/@mutation decorator)."""
        return "private"

    @query
    async def get_task(cls, task_id: int, include_owner: bool = True) -> TaskDTO | None:
        """Get a task by ID."""
        return TaskDTO(id=task_id, title="Test Task")


# ──────────────────────────────────────────────────
# Tests: UseCaseService
# ──────────────────────────────────────────────────


class TestUseCaseService:
    def test_discovers_decorated_methods(self):
        """Only @query/@mutation decorated methods are discovered."""
        assert "list_users" in UserService.__use_case_methods__
        assert "get_user" in UserService.__use_case_methods__
        assert "create_user" in UserService.__use_case_methods__
        assert "register" in UserService.__use_case_methods__

    def test_method_kind_stored_correctly(self):
        """Each discovered method has the correct kind."""
        assert UserService.__use_case_methods__["list_users"]["kind"] == "query"
        assert UserService.__use_case_methods__["get_user"]["kind"] == "query"
        assert UserService.__use_case_methods__["create_user"]["kind"] == "mutation"
        assert UserService.__use_case_methods__["register"]["kind"] == "mutation"

    def test_method_description_stored(self):
        """Each discovered method has description from docstring."""
        assert (
            UserService.__use_case_methods__["list_users"]["description"]
            == "Get all users."
        )

    def test_excludes_private_methods(self):
        """Methods starting with _ are excluded."""
        assert "_internal_helper" not in TaskService.__use_case_methods__

    def test_excludes_undecorated_async_classmethod(self):
        """Undecorated async classmethods are NOT discovered."""
        # _internal_helper is an async classmethod but without @query/@mutation
        assert "_internal_helper" not in TaskService.__use_case_methods__

    def test_excludes_get_tag_name(self):
        """get_tag_name is excluded from UseCase methods."""
        for service_cls in [UserService, TaskService]:
            assert "get_tag_name" not in service_cls.__use_case_methods__

    def test_get_tag_name_default(self):
        """get_tag_name returns the class name by default."""
        assert UserService.get_tag_name() == "UserService"
        assert TaskService.get_tag_name() == "TaskService"

    def test_get_tag_name_override(self):
        """get_tag_name can be overridden by subclass."""

        class MyService(UseCaseService):
            @classmethod
            def get_tag_name(cls) -> str:
                return "custom-tag"

        assert MyService.get_tag_name() == "custom-tag"

    def test_use_case_service_base_has_empty_methods(self):
        """UseCaseService base class has empty __use_case_methods__."""
        assert UseCaseService.__use_case_methods__ == {}

