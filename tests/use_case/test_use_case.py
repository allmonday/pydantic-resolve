"""Tests for the UseCase module — UseCaseService and ServiceIntrospector.

MCP server tests live in ``test_compose_mcp.py``.
"""

from __future__ import annotations

import uuid
import datetime
from decimal import Decimal
from typing import Annotated, Optional, TYPE_CHECKING

import pytest
from pydantic import BaseModel

from pydantic_resolve import query, mutation
from pydantic_resolve.use_case.business import UseCaseService
from pydantic_resolve.use_case.context import FromContext
from pydantic_resolve.use_case.introspector import (
    ServiceIntrospector,
    _generate_dto_sdl,
    _type_to_sdl_name,
)
from pydantic_resolve.use_case.types import UseCaseAppConfig

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


class SelectionMetaDTO(BaseModel):
    source: str


class SelectionUserDTO(BaseModel):
    id: int
    name: str
    email: str


class SelectionTaskDTO(BaseModel):
    id: int
    title: str
    owner: SelectionUserDTO | None = None
    watchers: list[SelectionUserDTO | None] = []
    metadata: dict = {}
    meta: SelectionMetaDTO | None = None


if TYPE_CHECKING:
    from tests.use_case.missing_forward_ref import MissingDTO


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


class SelectionService(UseCaseService):
    """Service for selection projection tests."""

    @query
    async def get_task(cls) -> SelectionTaskDTO:
        """Get a task with nested DTO fields."""
        return SelectionTaskDTO(
            id=1,
            title="Task 1",
            owner=SelectionUserDTO(id=10, name="Alice", email="a@example.com"),
            watchers=[SelectionUserDTO(id=11, name="Bob", email="b@example.com")],
            metadata={"priority": "high", "hidden": True},
            meta=SelectionMetaDTO(source="demo"),
        )

    @query
    async def list_tasks(cls) -> list[SelectionTaskDTO]:
        """List tasks with nested DTO fields."""
        return [await cls.get_task()]

    @query
    async def get_missing_owner(cls) -> SelectionTaskDTO:
        """Return a task with a nullable nested DTO set to None."""
        return SelectionTaskDTO(id=2, title="Task 2", owner=None)

    @query
    async def list_empty(cls) -> list[SelectionTaskDTO]:
        """Return an empty task list."""
        return []

    @query
    async def get_count(cls) -> int:
        """Return a non-Pydantic value."""
        return 1

    @query
    async def get_task_unresolved(cls) -> "MissingDTO":
        """Return a DTO instance while keeping an unresolved return annotation."""
        return await cls.get_task()

    @query
    async def list_users_with_gaps(cls) -> list[SelectionUserDTO | None]:
        """Return a list with nullable DTO items."""
        return [
            SelectionUserDTO(id=11, name="Bob", email="b@example.com"),
            None,
        ]

    @query
    async def get_task_with_missing_watcher(cls) -> SelectionTaskDTO:
        """Return a DTO with a nullable list element."""
        task = await cls.get_task()
        task.watchers = [
            SelectionUserDTO(id=11, name="Bob", email="b@example.com"),
            None,
        ]
        return task


class FutureAnnotationService(UseCaseService):
    """Service with future annotations and unresolved return type."""

    @query
    async def get_item(
        cls,
        game_id: uuid.UUID,
        limit: Optional[int] = 20,
    ) -> "MissingDTO":
        """Return type is intentionally unavailable at runtime."""
        return f"uuid:{game_id.version}:{limit}"


class FutureContextService(UseCaseService):
    """Service with FromContext param and unresolved return type."""

    @query
    async def get_my_item(
        cls,
        user_id: Annotated[int, FromContext()],
    ) -> "MissingDTO":
        """Return type is intentionally unavailable at runtime."""
        return f"user:{user_id}"


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


# ──────────────────────────────────────────────────
# Tests: _type_to_sdl_name
# ──────────────────────────────────────────────────


class TestTypeToSdlName:
    def test_int(self):
        assert _type_to_sdl_name(int) == "Int"

    def test_str(self):
        assert _type_to_sdl_name(str) == "String"

    def test_float(self):
        assert _type_to_sdl_name(float) == "Float"

    def test_bool(self):
        assert _type_to_sdl_name(bool) == "Boolean"

    def test_list_of_int(self):
        assert _type_to_sdl_name(list[int]) == "[Int!]!"

    def test_optional_int(self):
        assert _type_to_sdl_name(int | None) == "Int"

    def test_list_of_dto(self):
        assert _type_to_sdl_name(list[UserDTO]) == "[UserDTO!]!"

    def test_optional_dto(self):
        assert _type_to_sdl_name(UserDTO | None) == "UserDTO"

    def test_dto_class(self):
        assert _type_to_sdl_name(UserDTO) == "UserDTO"

    def test_dict(self):
        assert _type_to_sdl_name(dict) == "JSON"

    def test_empty_annotation(self):
        from inspect import Parameter

        assert _type_to_sdl_name(Parameter.empty) == "String"


# ──────────────────────────────────────────────────
# Tests: ServiceIntrospector
# ──────────────────────────────────────────────────


def _make_introspector() -> ServiceIntrospector:
    return ServiceIntrospector([UserService, TaskService])


class TestServiceIntrospector:
    def test_list_services(self):
        introspector = _make_introspector()
        services = introspector.list_services()
        assert len(services) == 2

        user_svc = next(s for s in services if s["name"] == "UserService")
        assert user_svc["description"] == "User management service."
        assert user_svc["methods_count"] == 4

        task_svc = next(s for s in services if s["name"] == "TaskService")
        assert task_svc["methods_count"] == 2  # list_tasks + get_task (excludes _internal)

    def test_describe_service_methods(self):
        introspector = _make_introspector()
        info = introspector.describe_service("UserService")
        assert info is not None
        assert info["name"] == "UserService"
        assert len(info["methods"]) == 4

    def test_describe_service_signatures(self):
        introspector = _make_introspector()
        info = introspector.describe_service("UserService")
        assert info is not None

        list_users = next(m for m in info["methods"] if m["name"] == "list_users")
        assert list_users["description"] == "Get all users."
        assert "list_users()" in list_users["signature"]
        assert "list[UserDTO]" in list_users["signature"]
        assert "[UserDTO!]!" in list_users["signature_sdl"]

        get_user = next(m for m in info["methods"] if m["name"] == "get_user")
        assert "user_id: int" in get_user["signature"]
        assert "UserDTO" in get_user["signature"]
        assert "user_id: Int!" in get_user["signature_sdl"]

    def test_describe_service_types(self):
        """types field contains SDL type definitions for referenced DTOs."""
        introspector = _make_introspector()
        info = introspector.describe_service("UserService")
        assert info is not None

        types_str = info["types"]
        assert "type UserDTO" in types_str
        assert "id: Int" in types_str
        assert "name: String!" in types_str

    def test_describe_service_task_types(self):
        """types includes nested DTOs from return values."""
        introspector = _make_introspector()
        info = introspector.describe_service("TaskService")
        assert info is not None

        types_str = info["types"]
        assert "type TaskDTO" in types_str
        assert "type UserDTO" in types_str
        assert "owner: UserDTO" in types_str

    def test_describe_service_with_params(self):
        introspector = _make_introspector()
        info = introspector.describe_service("UserService")
        assert info is not None

        get_user = next(m for m in info["methods"] if m["name"] == "get_user")
        assert "user_id" in get_user["parameters"]
        assert get_user["parameters"]["user_id"]["type"] == "integer"

    def test_describe_service_includes_selection_usage(self):
        introspector = ServiceIntrospector([SelectionService])
        info = introspector.describe_service("SelectionService")
        assert info is not None

        assert info["selection_usage"]["format"].startswith("Rootless GraphQL-like")
        assert "types" in info["selection_usage"]["source"]
        assert any("Nested Pydantic DTO fields require sub-selection." == rule for rule in info["selection_usage"]["rules"])

    def test_describe_service_marks_selection_capability_per_method(self):
        introspector = ServiceIntrospector([SelectionService])
        info = introspector.describe_service("SelectionService")
        assert info is not None

        get_task = next(m for m in info["methods"] if m["name"] == "get_task")
        assert get_task["selection_supported"] is True
        assert get_task["selection_example"] == "{ id owner { id name } }"

        get_count = next(m for m in info["methods"] if m["name"] == "get_count")
        assert get_count["selection_supported"] is False
        assert get_count["selection_example"] is None

        unresolved = next(m for m in info["methods"] if m["name"] == "get_task_unresolved")
        assert unresolved["selection_supported"] is None
        assert unresolved["selection_example"] is None

    def test_describe_service_not_found(self):
        introspector = _make_introspector()
        assert introspector.describe_service("nonexistent") is None

    def test_get_service(self):
        introspector = _make_introspector()
        assert introspector.get_service("UserService") is UserService
        assert introspector.get_service("nonexistent") is None

    def test_uses_class_docstring_as_description(self):
        introspector = _make_introspector()
        info = introspector.describe_service("TaskService")
        assert info is not None
        assert info["description"] == "Task management service."

