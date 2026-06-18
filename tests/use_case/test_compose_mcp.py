"""Tests for the UseCase GraphQL compose MCP server.

Covers ``create_use_case_graphql_mcp_server``:
- ``compose_query`` data queries (GraphQL-string multi-method composition)
- ``compose_query`` introspection queries (``__schema`` / ``__type``)
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


# ──────────────────────────────────────────────────
# compose_query — data queries
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


# ──────────────────────────────────────────────────
# compose_query — GraphQL introspection (multi-layer progressive)
# ──────────────────────────────────────────────────


class TestComposeQueryIntrospection:
    """``compose_query`` accepts standard GraphQL introspection queries for
    schema discovery. LLMs use ``__schema`` for overviews and ``__type``
    for drill-down into a specific DTO — no separate discovery tool needed.
    """

    @pytest.mark.asyncio
    async def test_schema_query_returns_services_and_methods(self, mcp_server):
        """Layer 1: ``__schema { queryType { fields { name } } }`` lists
        services (top-level fields on the Query type).

        Introspection responses are wrapped twice: the MCP envelope
        (``{success, data, hint}``) contains the standard GraphQL envelope
        (``{data, errors}``) under ``data``.
        """
        result = await mcp_server.call_tool(
            "compose_query",
            {
                "app_name": "project",
                "query": "{ __schema { queryType { fields { name } } } }",
            },
        )
        body = json.loads(result.content[0].text)
        assert body["success"] is True
        gql_data = body["data"]["data"]
        query_fields = gql_data["__schema"]["queryType"]["fields"]
        service_names = {f["name"] for f in query_fields}
        assert {"SprintService", "TaskService"} <= service_names

    @pytest.mark.asyncio
    async def test_type_query_drills_into_dto_fields(self, mcp_server):
        """Layer 2: ``__type(name: "X")`` returns one DTO's field list —
        the LLM uses this to discover what to put in the field-selection
        layer of a data query."""
        result = await mcp_server.call_tool(
            "compose_query",
            {
                "app_name": "project",
                "query": (
                    '{ __type(name: "TaskDTO") { '
                    "fields { name type { name kind ofType { name kind } } } } }"
                ),
            },
        )
        body = json.loads(result.content[0].text)
        assert body["success"] is True
        fields = body["data"]["data"]["__type"]["fields"]
        field_names = {f["name"] for f in fields}
        assert {"id", "title", "owner_id", "owner"} <= field_names

    @pytest.mark.asyncio
    async def test_type_query_drills_into_nested_dto(self, mcp_server):
        """Layer 3: the LLM can ask for the nested DTO (``OwnerDTO``) the
        same way — confirms the multi-layer drill-down works end-to-end
        and nested DTOs are reachable via introspection (this is the gap
        that motivated dropping the custom ``describe_compose_schema``)."""
        result = await mcp_server.call_tool(
            "compose_query",
            {
                "app_name": "project",
                "query": (
                    '{ __type(name: "OwnerDTO") { fields { name type { name kind } } } }'
                ),
            },
        )
        body = json.loads(result.content[0].text)
        assert body["success"] is True
        fields = body["data"]["data"]["__type"]["fields"]
        assert {f["name"] for f in fields} == {"id", "name"}

    @pytest.mark.asyncio
    async def test_typename_query(self, mcp_server):
        result = await mcp_server.call_tool(
            "compose_query",
            {"app_name": "project", "query": "{ __typename }"},
        )
        body = json.loads(result.content[0].text)
        assert body["success"] is True
        assert body["data"]["data"]["__typename"] == "Query"
