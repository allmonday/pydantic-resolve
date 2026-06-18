"""Tests for the UseCase GraphQL compose MCP server.

Covers ``create_use_case_graphql_mcp_server``:
- ``describe_compose_schema`` (compact schema discovery)
- ``compose_query`` (GraphQL-string multi-method composition)
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
# describe_compose_schema
# ──────────────────────────────────────────────────


class TestDescribeComposeSchema:
    @pytest.mark.asyncio
    async def test_returns_services_methods_args_returns_fields(self, mcp_server):
        result = await mcp_server.call_tool(
            "describe_compose_schema", {"app_name": "project"}
        )
        data = json.loads(result.content[0].text)["data"]
        assert "SprintService" in data["services"]
        assert "TaskService" in data["services"]

        task_svc = data["services"]["TaskService"]
        method_names = [m["name"] for m in task_svc["methods"]]
        assert "list_tasks" in method_names
        assert "get_task" in method_names
        assert "create_task" in method_names

        get_task = next(m for m in task_svc["methods"] if m["name"] == "get_task")
        assert get_task["kind"] == "query"
        assert get_task["returns"] == "Optional[TaskDTO]"
        arg_names = [a["name"] for a in get_task["args"]]
        assert arg_names == ["task_id", "include_owner"]
        task_id_arg = next(a for a in get_task["args"] if a["name"] == "task_id")
        assert task_id_arg["type"] == "int"
        include_owner_arg = next(
            a for a in get_task["args"] if a["name"] == "include_owner"
        )
        assert include_owner_arg.get("default") is True

        # Fields are exposed for the return DTO
        assert {f["name"] for f in get_task["fields"]} == {
            "id",
            "title",
            "owner_id",
            "owner",
        }
        # Nested DTO is marked so LLM knows to sub-select
        owner_field = next(f for f in get_task["fields"] if f["name"] == "owner")
        assert owner_field["nested"] is True

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
    async def test_hint_points_to_compose_query(self, mcp_server):
        result = await mcp_server.call_tool(
            "describe_compose_schema", {"app_name": "project"}
        )
        body = json.loads(result.content[0].text)
        hint = body["hint"]
        assert "compose_query" in hint
        # Hint must not cross-reference classic-server tools
        for forbidden in ("list_services", "describe_service", "call_use_case"):
            assert forbidden not in hint, (
                f"hint must not reference classic tool '{forbidden}'"
            )

    @pytest.mark.asyncio
    async def test_does_not_leak_from_context_params(
        self, mcp_server_with_context
    ):
        result = await mcp_server_with_context.call_tool(
            "describe_compose_schema", {"app_name": "project"}
        )
        data = json.loads(result.content[0].text)["data"]
        get_my_tasks = next(
            m
            for m in data["services"]["ContextService"]["methods"]
            if m["name"] == "get_my_tasks"
        )
        # user_id is server-injected via FromContext — must NOT appear as a query arg
        arg_names = [a["name"] for a in get_my_tasks["args"]]
        assert "user_id" not in arg_names
        assert arg_names == []


# ──────────────────────────────────────────────────
# compose_query via the GraphQL MCP server
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
    async def test_introspection_query_rejected_with_helpful_hint(
        self, mcp_server
    ):
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
        # Must steer the LLM toward the GraphQL discovery tool, not classic tools
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
