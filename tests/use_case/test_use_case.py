"""Tests for the UseCase module — UseCaseService, ServiceIntrospector, and MCP server."""

from __future__ import annotations

import json
from typing import Annotated

import pytest
from pydantic import BaseModel

from pydantic_resolve.use_case.business import UseCaseService
from pydantic_resolve.use_case.context import FromContext
from pydantic_resolve.use_case.introspector import (
    ServiceIntrospector,
    _generate_dto_sdl,
    _type_to_sdl_name,
)
from pydantic_resolve.use_case.server import create_use_case_mcp_server
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


# ──────────────────────────────────────────────────
# Test Services
# ──────────────────────────────────────────────────


class UserService(UseCaseService):
    """User management service."""

    @classmethod
    async def list_users(cls) -> list[UserDTO]:
        """Get all users."""
        return [UserDTO(id=1, name="Alice"), UserDTO(id=2, name="Bob")]

    @classmethod
    async def get_user(cls, user_id: int) -> UserDTO | None:
        """Get a user by ID."""
        if user_id == 1:
            return UserDTO(id=1, name="Alice")
        return None

    @classmethod
    async def create_user(cls, name: str, email: str) -> UserDTO:
        """Create a new user."""
        return UserDTO(id=99, name=name)

    @classmethod
    async def register(cls, data: CreateUserDTO) -> UserDTO:
        """Register a new user."""
        return UserDTO(id=99, name=data.name)


class TaskService(UseCaseService):
    """Task management service."""

    @classmethod
    async def list_tasks(cls) -> list[TaskDTO]:
        """Get all tasks."""
        return [
            TaskDTO(id=1, title="Task 1", owner=UserDTO(id=1, name="Alice")),
        ]

    @classmethod
    async def _internal_helper(cls) -> str:
        """This should NOT be exposed."""
        return "private"

    @classmethod
    async def get_task(cls, task_id: int, include_owner: bool = True) -> TaskDTO | None:
        """Get a task by ID."""
        return TaskDTO(id=task_id, title="Test Task")


# ──────────────────────────────────────────────────
# Tests: UseCaseService
# ──────────────────────────────────────────────────


class TestUseCaseService:
    def test_discovers_async_classmethods(self):
        """Public async classmethods are discovered."""
        assert "list_users" in UserService.__use_case_methods__
        assert "get_user" in UserService.__use_case_methods__
        assert "create_user" in UserService.__use_case_methods__

    def test_excludes_private_methods(self):
        """Methods starting with _ are excluded."""
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


# ──────────────────────────────────────────────────
# Tests: MCP Server (integration)
# ──────────────────────────────────────────────────


@pytest.fixture
def mcp_server():
    return create_use_case_mcp_server(
        apps=[
            UseCaseAppConfig(
                name="project",
                description="Project management",
                services=[UserService, TaskService],
            ),
        ],
        name="Test UseCase API",
    )


@pytest.fixture
def multi_app_server():
    return create_use_case_mcp_server(
        apps=[
            UseCaseAppConfig(
                name="project",
                description="Project management",
                services=[UserService, TaskService],
            ),
            UseCaseAppConfig(
                name="system",
                description="System operations",
                services=[UserService],
            ),
        ],
        name="Multi-App UseCase API",
    )


class TestUseCaseMcpServer:
    def test_server_creation(self, mcp_server):
        """Server is created successfully."""
        assert mcp_server is not None

    @pytest.mark.asyncio
    async def test_list_apps(self, multi_app_server):
        """list_apps returns all registered apps."""
        result = await multi_app_server.call_tool("list_apps", {})
        data = json.loads(result.content[0].text)
        assert data["success"] is True
        assert len(data["data"]) == 2

        names = [a["name"] for a in data["data"]]
        assert "project" in names
        assert "system" in names

    @pytest.mark.asyncio
    async def test_list_apps_hint(self, multi_app_server):
        """list_apps returns helpful hint with app names."""
        result = await multi_app_server.call_tool("list_apps", {})
        data = json.loads(result.content[0].text)
        assert "hint" in data
        assert "project" in data["hint"]

    @pytest.mark.asyncio
    async def test_list_services_tool(self, mcp_server):
        """list_services returns all registered services for an app."""
        result = await mcp_server.call_tool(
            "list_services", {"app_name": "project"}
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is True
        assert len(data["data"]) == 2

    @pytest.mark.asyncio
    async def test_list_services_app_not_found(self, mcp_server):
        """list_services returns error for unknown app."""
        result = await mcp_server.call_tool(
            "list_services", {"app_name": "unknown"}
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_describe_service_tool(self, mcp_server):
        """describe_service returns method details with SDL signatures."""
        result = await mcp_server.call_tool(
            "describe_service",
            {"app_name": "project", "service_name": "UserService"},
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is True
        assert data["data"]["name"] == "UserService"
        assert len(data["data"]["methods"]) == 4
        # Check that types field has SDL
        assert "type UserDTO" in data["data"]["types"]

    @pytest.mark.asyncio
    async def test_describe_service_not_found(self, mcp_server):
        """describe_service returns error for unknown service."""
        result = await mcp_server.call_tool(
            "describe_service",
            {"app_name": "project", "service_name": "unknown"},
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_describe_service_app_not_found(self, mcp_server):
        """describe_service returns error for unknown app."""
        result = await mcp_server.call_tool(
            "describe_service",
            {"app_name": "unknown", "service_name": "UserService"},
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_call_use_case_no_params(self, mcp_server):
        """call_use_case works with no parameters."""
        result = await mcp_server.call_tool(
            "call_use_case",
            {
                "app_name": "project",
                "service_name": "UserService",
                "method_name": "list_users",
                "params": "{}",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is True
        assert len(data["data"]) == 2
        assert data["data"][0]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_call_use_case_with_params(self, mcp_server):
        """call_use_casepasses parameters to the method."""
        result = await mcp_server.call_tool(
            "call_use_case",
            {
                "app_name": "project",
                "service_name": "UserService",
                "method_name": "get_user",
                "params": json.dumps({"user_id": 1}),
            },
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is True
        assert data["data"]["id"] == 1
        assert data["data"]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_call_use_case_returns_null(self, mcp_server):
        """call_use_casehandles None return values."""
        result = await mcp_server.call_tool(
            "call_use_case",
            {
                "app_name": "project",
                "service_name": "UserService",
                "method_name": "get_user",
                "params": json.dumps({"user_id": 999}),
            },
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is True
        assert data["data"] is None

    @pytest.mark.asyncio
    async def test_call_use_case_app_not_found(self, mcp_server):
        """call_use_casereturns error for unknown app."""
        result = await mcp_server.call_tool(
            "call_use_case",
            {
                "app_name": "unknown",
                "service_name": "UserService",
                "method_name": "foo",
                "params": "{}",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_call_use_case_service_not_found(self, mcp_server):
        """call_use_casereturns error for unknown service."""
        result = await mcp_server.call_tool(
            "call_use_case",
            {
                "app_name": "project",
                "service_name": "unknown",
                "method_name": "foo",
                "params": "{}",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_call_use_case_method_not_found(self, mcp_server):
        """call_use_casereturns error for unknown method."""
        result = await mcp_server.call_tool(
            "call_use_case",
            {
                "app_name": "project",
                "service_name": "UserService",
                "method_name": "nonexistent",
                "params": "{}",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_call_use_case_invalid_json(self, mcp_server):
        """call_use_casereturns error for invalid JSON params."""
        result = await mcp_server.call_tool(
            "call_use_case",
            {
                "app_name": "project",
                "service_name": "UserService",
                "method_name": "list_users",
                "params": "invalid",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_call_use_case_invalid_param_type(self, mcp_server):
        """call_use_casereturns error when params is not a dict."""
        result = await mcp_server.call_tool(
            "call_use_case",
            {
                "app_name": "project",
                "service_name": "UserService",
                "method_name": "list_users",
                "params": "[1,2]",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_call_use_case_wrong_param_name(self, mcp_server):
        """call_use_casereturns error when parameter name doesn't match."""
        result = await mcp_server.call_tool(
            "call_use_case",
            {
                "app_name": "project",
                "service_name": "UserService",
                "method_name": "get_user",
                "params": json.dumps({"wrong_param": 1}),
            },
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is False


# ──────────────────────────────────────────────────
# Tests: Bug fixes — SDL type fidelity, param DTOs, required flag
# ──────────────────────────────────────────────────


class TestSDLSignatureTypeFidelity:
    """Issue 1: SDL signature should preserve DTO names, list syntax, etc."""

    def test_dto_param_uses_class_name(self):
        """DTO parameters use class name in SDL, not 'JSON'."""
        introspector = _make_introspector()
        info = introspector.describe_service("UserService")
        assert info is not None
        register = next(m for m in info["methods"] if m["name"] == "register")
        assert "data: CreateUserDTO!" in register["signature_sdl"]

    def test_list_param_renders_correctly(self):
        """list[int] parameters render as [Int!]! in SDL, not 'array!'."""
        introspector = ServiceIntrospector([ListParamService])
        info = introspector.describe_service("ListParamService")
        assert info is not None
        batch = next(m for m in info["methods"] if m["name"] == "batch")
        assert "ids: [Int!]!" in batch["signature_sdl"]


class TestParamDTOCollection:
    """Issue 2: DTOs used as parameters should appear in the types field."""

    def test_dto_types_collected_from_params(self):
        introspector = _make_introspector()
        info = introspector.describe_service("UserService")
        assert info is not None
        types_str = info["types"]
        assert "type CreateUserDTO" in types_str
        assert "name: String!" in types_str
        assert "email: String!" in types_str


class TestParamRequiredFlag:
    """Issue 3: Parameters with defaults should not be marked required."""

    def test_optional_params_not_required_in_sdl(self):
        """Parameters with default values are not marked as required (!)."""
        introspector = ServiceIntrospector([TaskService])
        info = introspector.describe_service("TaskService")
        assert info is not None
        get_task = next(m for m in info["methods"] if m["name"] == "get_task")
        # task_id has no default -> required
        assert "task_id: Int!" in get_task["signature_sdl"]
        # include_owner has default=True -> optional (no !)
        assert "include_owner: Boolean" in get_task["signature_sdl"]
        assert "include_owner: Boolean!" not in get_task["signature_sdl"]

    def test_parameters_dict_includes_required(self):
        """Parameter JSON Schema includes 'required' flag."""
        introspector = ServiceIntrospector([TaskService])
        info = introspector.describe_service("TaskService")
        assert info is not None
        get_task = next(m for m in info["methods"] if m["name"] == "get_task")
        assert get_task["parameters"]["task_id"]["required"] is True
        assert get_task["parameters"]["include_owner"]["required"] is False


# ──────────────────────────────────────────────────
# Auxiliary test service for list param testing
# ──────────────────────────────────────────────────


class ListParamService(UseCaseService):
    """Service with list parameters."""

    @classmethod
    async def batch(cls, ids: list[int]) -> list[UserDTO]:
        """Batch get users."""
        return []


# ──────────────────────────────────────────────────
# Tests: Fix 4 — get_type_hints fallback
# ──────────────────────────────────────────────────


class ForwardRefService(UseCaseService):
    """Service with forward reference."""

    @classmethod
    async def run(cls, x: int, payload: "MissingType") -> str:  # noqa: F821
        """Run with forward ref."""
        return ""


class TestForwardRefFallback:
    """Fix 4: When get_type_hints fails, resolvable params still get correct types."""

    def test_resolvable_param_uses_annotation_fallback(self):
        introspector = ServiceIntrospector([ForwardRefService])
        info = introspector.describe_service("ForwardRefService")
        assert info is not None
        run_method = info["methods"][0]
        # x: int resolved via param.annotation fallback
        assert "x: Int!" in run_method["signature_sdl"]
        # payload: "MissingType" falls back to string annotation -> String
        assert "payload: String!" in run_method["signature_sdl"]

    def test_parameters_dict_consistent_with_sdl(self):
        """parameters dict and SDL should not contradict each other."""
        introspector = ServiceIntrospector([ForwardRefService])
        info = introspector.describe_service("ForwardRefService")
        run_method = info["methods"][0]
        # x is int in both parameters and SDL
        assert run_method["parameters"]["x"]["type"] == "integer"
        assert "x: Int!" in run_method["signature_sdl"]


# ──────────────────────────────────────────────────
# Tests: Fix 5 — Optional list nullability
# ──────────────────────────────────────────────────


class OptionalListDTO(BaseModel):
    items: list[int] | None = None


# ──────────────────────────────────────────────────
# Tests: context_extractor support
# ──────────────────────────────────────────────────


class ContextAwareService(UseCaseService):
    """Service with FromContext-annotated methods."""

    @classmethod
    async def get_my_items(cls, user_id: Annotated[int, FromContext()]) -> list[str]:
        """Return items filtered by user_id."""
        if user_id == 1:
            return ["alice_item_1", "alice_item_2"]
        return [f"user_{user_id}_item"]

    @classmethod
    async def get_my_items_with_tenant(
        cls,
        user_id: Annotated[int, FromContext()],
        tenant_id: Annotated[str, FromContext()],
    ) -> list[str]:
        """Return items filtered by user_id and tenant_id."""
        return [f"{tenant_id}:{user_id}_item"]

    @classmethod
    async def get_optional_item(
        cls,
        user_id: Annotated[int, FromContext()] = 0,
    ) -> list[str]:
        """Return items with optional user_id from context."""
        if user_id == 0:
            return ["guest_item"]
        return [f"user_{user_id}_item"]

    @classmethod
    async def list_items(cls) -> list[str]:
        """Return all items (no context needed)."""
        return ["item_1", "item_2"]


class TestFromContext:
    """Tests for FromContext annotation support in UseCaseAppConfig."""

    @pytest.mark.asyncio
    async def test_from_context_param_injected(self):
        """FromContext parameter receives value from context_extractor."""

        def my_extractor(ctx) -> dict:
            return {"user_id": 1}

        server = create_use_case_mcp_server(
            apps=[
                UseCaseAppConfig(
                    name="test",
                    services=[ContextAwareService],
                    context_extractor=my_extractor,
                ),
            ],
        )
        result = await server.call_tool(
            "call_use_case",
            {
                "app_name": "test",
                "service_name": "ContextAwareService",
                "method_name": "get_my_items",
                "params": "{}",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is True
        assert data["data"] == ["alice_item_1", "alice_item_2"]

    @pytest.mark.asyncio
    async def test_multiple_from_context_params(self):
        """Multiple FromContext parameters are all injected."""

        def my_extractor(ctx) -> dict:
            return {"user_id": 1, "tenant_id": "acme"}

        server = create_use_case_mcp_server(
            apps=[
                UseCaseAppConfig(
                    name="test",
                    services=[ContextAwareService],
                    context_extractor=my_extractor,
                ),
            ],
        )
        result = await server.call_tool(
            "call_use_case",
            {
                "app_name": "test",
                "service_name": "ContextAwareService",
                "method_name": "get_my_items_with_tenant",
                "params": "{}",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is True
        assert data["data"] == ["acme:1_item"]

    @pytest.mark.asyncio
    async def test_non_from_context_method_unaffected(self):
        """Methods without FromContext parameters work normally."""

        def my_extractor(ctx) -> dict:
            return {"user_id": 1}

        server = create_use_case_mcp_server(
            apps=[
                UseCaseAppConfig(
                    name="test",
                    services=[ContextAwareService],
                    context_extractor=my_extractor,
                ),
            ],
        )
        result = await server.call_tool(
            "call_use_case",
            {
                "app_name": "test",
                "service_name": "ContextAwareService",
                "method_name": "list_items",
                "params": "{}",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is True
        assert data["data"] == ["item_1", "item_2"]

    @pytest.mark.asyncio
    async def test_required_from_context_missing_returns_error(self):
        """Required FromContext parameter missing from context returns error."""

        def my_extractor(ctx) -> dict:
            return {}  # no user_id

        server = create_use_case_mcp_server(
            apps=[
                UseCaseAppConfig(
                    name="test",
                    services=[ContextAwareService],
                    context_extractor=my_extractor,
                ),
            ],
        )
        result = await server.call_tool(
            "call_use_case",
            {
                "app_name": "test",
                "service_name": "ContextAwareService",
                "method_name": "get_my_items",
                "params": "{}",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is False
        assert "user_id" in data["error"]

    @pytest.mark.asyncio
    async def test_optional_from_context_uses_default(self):
        """FromContext parameter with default uses default when context is empty."""

        def my_extractor(ctx) -> dict:
            return {}  # no user_id

        server = create_use_case_mcp_server(
            apps=[
                UseCaseAppConfig(
                    name="test",
                    services=[ContextAwareService],
                    context_extractor=my_extractor,
                ),
            ],
        )
        result = await server.call_tool(
            "call_use_case",
            {
                "app_name": "test",
                "service_name": "ContextAwareService",
                "method_name": "get_optional_item",
                "params": "{}",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is True
        assert data["data"] == ["guest_item"]

    @pytest.mark.asyncio
    async def test_no_context_extractor_required_param_fails(self):
        """Without context_extractor, required FromContext param fails."""

        server = create_use_case_mcp_server(
            apps=[
                UseCaseAppConfig(
                    name="test",
                    services=[ContextAwareService],
                ),
            ],
        )
        result = await server.call_tool(
            "call_use_case",
            {
                "app_name": "test",
                "service_name": "ContextAwareService",
                "method_name": "get_my_items",
                "params": "{}",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is False
        assert "user_id" in data["error"]

    @pytest.mark.asyncio
    async def test_no_context_extractor_optional_param_uses_default(self):
        """Without context_extractor, optional FromContext param uses default."""

        server = create_use_case_mcp_server(
            apps=[
                UseCaseAppConfig(
                    name="test",
                    services=[ContextAwareService],
                ),
            ],
        )
        result = await server.call_tool(
            "call_use_case",
            {
                "app_name": "test",
                "service_name": "ContextAwareService",
                "method_name": "get_optional_item",
                "params": "{}",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is True
        assert data["data"] == ["guest_item"]

    @pytest.mark.asyncio
    async def test_async_context_extractor(self):
        """Async context_extractor functions are supported."""

        async def async_extractor(ctx) -> dict:
            return {"user_id": 1}

        server = create_use_case_mcp_server(
            apps=[
                UseCaseAppConfig(
                    name="test",
                    services=[ContextAwareService],
                    context_extractor=async_extractor,
                ),
            ],
        )
        result = await server.call_tool(
            "call_use_case",
            {
                "app_name": "test",
                "service_name": "ContextAwareService",
                "method_name": "get_my_items",
                "params": "{}",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is True
        assert data["data"] == ["alice_item_1", "alice_item_2"]


class TestOptionalListNullability:
    """Fix 5: list[X] | None should produce [X!], not [X!]!."""

    def test_optional_list_sdl_name(self):
        assert _type_to_sdl_name(list[int] | None) == "[Int!]"

    def test_optional_list_nullable_in_dto_sdl(self):
        sdl = _generate_dto_sdl(OptionalListDTO)
        assert "items: [Int!]" in sdl
        assert "items: [Int!]!" not in sdl

    def test_non_optional_list_still_required(self):
        """list[X] (without None) should still produce [X!]!."""
        assert _type_to_sdl_name(list[int]) == "[Int!]!"
