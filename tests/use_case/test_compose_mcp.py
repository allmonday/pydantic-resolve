"""Tests for the UseCase GraphQL compose MCP server.

Covers ``create_use_case_graphql_mcp_server`` 4-layer progressive
disclosure:
- Layer 1: ``list_apps`` (cheap app discovery)
- Layer 2: ``describe_compose_schema`` (services + method listing)
- Layer 3: ``describe_compose_method`` (per-method detail)
- Layer 4: ``compose_query`` (data execution; introspection rejected)
"""

from __future__ import annotations

import json
from typing import Annotated, Optional

import pytest
from pydantic import BaseModel

from pydantic_resolve import query, mutation
from pydantic_resolve.use_case.business import UseCaseService
from pydantic_resolve.use_case.context import FromContext
from pydantic_resolve.use_case.server_graphql import create_use_case_graphql_mcp_server
from pydantic_resolve.use_case.types import UseCaseAppConfig


# ──────────────────────────────────────────────────
# DTOs and services
# ──────────────────────────────────────────────────


class OwnerDTO(BaseModel):
    id: int
    name: str


class TaskDTO(BaseModel):
    id: int
    title: str
    owner_id: int
    owner: Optional[OwnerDTO] = None

    def resolve_owner(self):
        return OwnerDTO(id=self.owner_id, name=f"User{self.owner_id}")


class SprintDTO(BaseModel):
    id: int
    name: str
    task_count: int = 0


class SprintService(UseCaseService):
    """Sprint service."""

    @query
    async def list_sprints(cls) -> list[SprintDTO]:
        """List all sprints."""
        return [
            SprintDTO(id=1, name="Sprint A"),
            SprintDTO(id=2, name="Sprint B"),
        ]

    @query
    async def get_sprint(cls, sprint_id: int) -> Optional[SprintDTO]:
        """Get a sprint by ID."""
        if sprint_id == 1:
            return SprintDTO(id=1, name="Sprint A")
        return None


class TaskService(UseCaseService):
    """Task service."""

    @query
    async def list_tasks(cls) -> list[TaskDTO]:
        """List all tasks."""
        return [
            TaskDTO(id=10, title="Task 10", owner_id=1),
            TaskDTO(id=11, title="Task 11", owner_id=2),
        ]

    @query
    async def get_task(
        cls, task_id: int, include_owner: bool = True
    ) -> Optional[TaskDTO]:
        """Get a task by ID."""
        return TaskDTO(id=task_id, title=f"Task {task_id}", owner_id=1)

    @mutation
    async def create_task(cls, title: str) -> TaskDTO:
        """Create a task."""
        return TaskDTO(id=99, title=title, owner_id=1)


class ContextService(UseCaseService):
    """Service demonstrating FromContext param."""

    @query
    async def get_my_tasks(
        cls, user_id: Annotated[int, FromContext()]
    ) -> list[TaskDTO]:
        """Return tasks for the calling user."""
        return [
            TaskDTO(id=task_id, title=f"Task of {user_id}", owner_id=user_id)
            for task_id in (1, 2)
        ]


# ──────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────


@pytest.fixture
def mcp_server():
    return create_use_case_graphql_mcp_server(
        apps=[
            UseCaseAppConfig(
                name="project",
                description="Project management",
                services=[SprintService, TaskService],
            ),
        ],
        name="Compose Test API",
    )


@pytest.fixture
def mcp_server_with_context():
    return create_use_case_graphql_mcp_server(
        apps=[
            UseCaseAppConfig(
                name="project",
                description="Project management",
                services=[ContextService],
                context_extractor=lambda ctx: {"user_id": ctx.get("user_id", 0)},
            ),
        ],
        name="Compose Context Test API",
    )


# ──────────────────────────────────────────────────
# Layer 1: list_apps
# ──────────────────────────────────────────────────


class TestListApps:
    @pytest.mark.asyncio
    async def test_returns_app_metadata(self, mcp_server):
        result = await mcp_server.call_tool("list_apps", {})
        body = json.loads(result.content[0].text)
        assert body["success"] is True
        assert body["data"] == [
            {
                "name": "project",
                "description": "Project management",
                "services_count": 2,
            }
        ]

    @pytest.mark.asyncio
    async def test_hint_points_to_describe_compose_schema(self, mcp_server):
        result = await mcp_server.call_tool("list_apps", {})
        body = json.loads(result.content[0].text)
        assert "describe_compose_schema" in body["hint"]
        assert "project" in body["hint"]


# ──────────────────────────────────────────────────
# Layer 2: describe_compose_schema (services + methods listing only)
# ──────────────────────────────────────────────────


class TestDescribeComposeSchema:
    @pytest.mark.asyncio
    async def test_returns_services_and_methods_only(self, mcp_server):
        """Layer 2 is intentionally lightweight: just service/method
        names + kinds + descriptions. No args, return types, or DTO
        fields — those live in Layer 3 to keep this response compact.
        """
        result = await mcp_server.call_tool(
            "describe_compose_schema", {"app_name": "project"}
        )
        data = json.loads(result.content[0].text)["data"]
        assert set(data["services"].keys()) == {"SprintService", "TaskService"}

        task_svc = data["services"]["TaskService"]
        assert task_svc["description"] == "Task service."

        method_names = [m["name"] for m in task_svc["methods"]]
        assert {"list_tasks", "get_task", "create_task"} == set(method_names)

        # Each method entry is minimal — name, kind, description only
        for method in task_svc["methods"]:
            assert set(method.keys()) == {"name", "kind", "description"}
        # Args / returns / fields must NOT leak into Layer 2
        get_task = next(m for m in task_svc["methods"] if m["name"] == "get_task")
        assert "args" not in get_task
        assert "returns" not in get_task
        assert "fields" not in get_task

    @pytest.mark.asyncio
    async def test_mutation_filtered_when_disabled(self):
        server = create_use_case_graphql_mcp_server(
            apps=[
                UseCaseAppConfig(
                    name="project",
                    services=[TaskService],
                    enable_mutation=False,
                ),
            ],
        )
        result = await server.call_tool(
            "describe_compose_schema", {"app_name": "project"}
        )
        data = json.loads(result.content[0].text)["data"]
        methods = data["services"]["TaskService"]["methods"]
        assert all(m["kind"] != "mutation" for m in methods)
        assert "create_task" not in [m["name"] for m in methods]

    @pytest.mark.asyncio
    async def test_app_not_found_returns_error_envelope(self, mcp_server):
        result = await mcp_server.call_tool(
            "describe_compose_schema", {"app_name": "no_such_app"}
        )
        body = json.loads(result.content[0].text)
        assert body["success"] is False
        assert body["error_type"] == "app_not_found"
        assert "no_such_app" in body["error"]
        assert "project" in body["error"]  # lists available apps

    @pytest.mark.asyncio
    async def test_hint_points_to_describe_compose_method(self, mcp_server):
        """Layer 2 hint drills into Layer 3, not Layer 4 — the LLM needs
        method args / return types / DTO fields before it can write a
        compose query."""
        result = await mcp_server.call_tool(
            "describe_compose_schema", {"app_name": "project"}
        )
        body = json.loads(result.content[0].text)
        hint = body["hint"]
        assert "describe_compose_method" in hint
        # Hint must not cross-reference classic-server tools
        for forbidden in ("list_services", "describe_service", "call_use_case"):
            assert forbidden not in hint, (
                f"hint must not reference classic tool '{forbidden}'"
            )


# ──────────────────────────────────────────────────
# Layer 3: describe_compose_method (per-method detail)
# ──────────────────────────────────────────────────


class TestDescribeComposeMethod:
    @pytest.mark.asyncio
    async def test_returns_args_returns_and_fields(self, mcp_server):
        result = await mcp_server.call_tool(
            "describe_compose_method",
            {
                "app_name": "project",
                "service_name": "TaskService",
                "method_name": "get_task",
            },
        )
        body = json.loads(result.content[0].text)
        assert body["success"] is True
        method = body["data"]
        assert method["name"] == "get_task"
        assert method["kind"] == "query"
        assert method["returns"] == "Optional[TaskDTO]"

        # Args include types and defaults
        arg_names = [a["name"] for a in method["args"]]
        assert arg_names == ["task_id", "include_owner"]
        task_id_arg = next(a for a in method["args"] if a["name"] == "task_id")
        assert task_id_arg["type"] == "int"
        include_owner_arg = next(
            a for a in method["args"] if a["name"] == "include_owner"
        )
        assert include_owner_arg.get("default") is True

        # Top-level DTO fields are exposed
        assert {f["name"] for f in method["fields"]} == {
            "id",
            "title",
            "owner_id",
            "owner",
        }
        # Nested DTO is marked but not expanded
        owner_field = next(f for f in method["fields"] if f["name"] == "owner")
        assert owner_field["nested"] is True

    @pytest.mark.asyncio
    async def test_app_not_found(self, mcp_server):
        result = await mcp_server.call_tool(
            "describe_compose_method",
            {
                "app_name": "no_such_app",
                "service_name": "TaskService",
                "method_name": "get_task",
            },
        )
        body = json.loads(result.content[0].text)
        assert body["success"] is False
        assert body["error_type"] == "app_not_found"

    @pytest.mark.asyncio
    async def test_service_not_found(self, mcp_server):
        result = await mcp_server.call_tool(
            "describe_compose_method",
            {
                "app_name": "project",
                "service_name": "NoSuchService",
                "method_name": "get_task",
            },
        )
        body = json.loads(result.content[0].text)
        assert body["success"] is False
        assert body["error_type"] == "type_not_found"
        assert "NoSuchService" in body["error"]
        # Lists available services so LLM can self-correct
        assert "TaskService" in body["error"]

    @pytest.mark.asyncio
    async def test_method_not_found(self, mcp_server):
        result = await mcp_server.call_tool(
            "describe_compose_method",
            {
                "app_name": "project",
                "service_name": "TaskService",
                "method_name": "no_such_method",
            },
        )
        body = json.loads(result.content[0].text)
        assert body["success"] is False
        assert body["error_type"] == "operation_not_found"
        assert "no_such_method" in body["error"]
        # Lists available methods so LLM can self-correct
        assert "list_tasks" in body["error"]
        assert "get_task" in body["error"]

    @pytest.mark.asyncio
    async def test_mutation_rejected_when_disabled(self):
        server = create_use_case_graphql_mcp_server(
            apps=[
                UseCaseAppConfig(
                    name="project",
                    services=[TaskService],
                    enable_mutation=False,
                ),
            ],
        )
        result = await server.call_tool(
            "describe_compose_method",
            {
                "app_name": "project",
                "service_name": "TaskService",
                "method_name": "create_task",
            },
        )
        body = json.loads(result.content[0].text)
        assert body["success"] is False
        assert body["error_type"] == "operation_not_found"
        assert "mutation" in body["error"].lower()

    @pytest.mark.asyncio
    async def test_does_not_leak_from_context_params(
        self, mcp_server_with_context
    ):
        """user_id is server-injected via FromContext — must NOT appear
        as a query arg in the method detail (clients cannot set it)."""
        result = await mcp_server_with_context.call_tool(
            "describe_compose_method",
            {
                "app_name": "project",
                "service_name": "ContextService",
                "method_name": "get_my_tasks",
            },
        )
        body = json.loads(result.content[0].text)
        method = body["data"]
        arg_names = [a["name"] for a in method["args"]]
        assert "user_id" not in arg_names
        assert arg_names == []

    @pytest.mark.asyncio
    async def test_hint_points_to_compose_query(self, mcp_server):
        """Layer 3 hint drills into Layer 4 (execution)."""
        result = await mcp_server.call_tool(
            "describe_compose_method",
            {
                "app_name": "project",
                "service_name": "TaskService",
                "method_name": "get_task",
            },
        )
        body = json.loads(result.content[0].text)
        assert "compose_query" in body["hint"]
        assert "TaskService" in body["hint"]
        assert "get_task" in body["hint"]


# ──────────────────────────────────────────────────
# Layer 4: compose_query (data only; introspection rejected)
# ──────────────────────────────────────────────────


class TestComposeQueryTool:
    @pytest.mark.asyncio
    async def test_compose_query_tool_success(self, mcp_server):
        result = await mcp_server.call_tool(
            "compose_query",
            {
                "app_name": "project",
                "query": "{ SprintService { list_sprints { id name } } }",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is True
        assert (
            data["data"]["SprintService"]["list_sprints"][0]["name"] == "Sprint A"
        )

    @pytest.mark.asyncio
    async def test_compose_query_tool_error_envelope(self, mcp_server):
        result = await mcp_server.call_tool(
            "compose_query",
            {"app_name": "project", "query": "{ NoSuchService { x { id } } }"},
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is False
        assert data["error_type"] == "type_not_found"
        assert "NoSuchService" in data["error"]

    @pytest.mark.asyncio
    async def test_compose_query_tool_app_not_found(self, mcp_server):
        result = await mcp_server.call_tool(
            "compose_query",
            {
                "app_name": "no_such_app",
                "query": "{ SprintService { list_sprints { id } } }",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is False
        assert data["error_type"] == "app_not_found"

    @pytest.mark.asyncio
    async def test_introspection_rejected_with_hint_to_layer_2(self, mcp_server):
        """Layer 4 rejects ``__schema`` / ``__type`` / ``__typename`` and
        redirects the LLM to ``describe_compose_schema`` (Layer 2). Layers
        2/3 own schema discovery; Layer 4 owns execution — clean
        separation.
        """
        result = await mcp_server.call_tool(
            "compose_query",
            {
                "app_name": "project",
                "query": "{ __schema { types { name } } }",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is False
        assert data["error_type"] == "validation_error"
        assert "describe_compose_schema" in data["error"]
        for forbidden in ("describe_service", "list_services", "call_use_case"):
            assert forbidden not in data["error"]

    @pytest.mark.asyncio
    async def test_success_hint_does_not_reference_classic_tools(
        self, mcp_server
    ):
        """The GraphQL server is independent — hints must not cross-reference
        classic-server tools. Regression for the prior mixed-server design
        where compose_query's hint mentioned describe_service / list_services.
        """
        result = await mcp_server.call_tool(
            "compose_query",
            {
                "app_name": "project",
                "query": "{ SprintService { list_sprints { id } } }",
            },
        )
        data = json.loads(result.content[0].text)
        hint = data["hint"]
        for forbidden in ("describe_service", "list_services", "call_use_case"):
            assert forbidden not in hint, (
                f"compose_query hint must not reference classic tool '{forbidden}'"
            )
