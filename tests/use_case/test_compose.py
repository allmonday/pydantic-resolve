"""Tests for UseCase compose_query — GraphQL-style multi-method composition."""

from __future__ import annotations

import json
from typing import Annotated, Optional

import pytest
from pydantic import BaseModel

from pydantic_resolve import query, mutation
from pydantic_resolve.use_case.business import UseCaseService
from pydantic_resolve.use_case.compose import ComposeError, compose_and_resolve
from pydantic_resolve.use_case.context import FromContext
from pydantic_resolve.use_case.manager import UseCaseManager
from pydantic_resolve.use_case.server import create_use_case_mcp_server
from pydantic_resolve.use_case.types import UseCaseAppConfig


# ──────────────────────────────────────────────────
# DTOs
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


# ──────────────────────────────────────────────────
# Services
# ──────────────────────────────────────────────────


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
        return [TaskDTO(id=task_id, title=f"Task of {user_id}", owner_id=user_id) for task_id in (1, 2)]


# ──────────────────────────────────────────────────
# Manager / app fixtures
# ──────────────────────────────────────────────────


def _make_manager(*, enable_mutation: bool = True, context_extractor=None) -> UseCaseManager:
    return UseCaseManager(
        apps=[
            UseCaseAppConfig(
                name="project",
                description="project app",
                services=[SprintService, TaskService],
                enable_mutation=enable_mutation,
                context_extractor=context_extractor,
            ),
        ],
    )


def _make_context_manager() -> UseCaseManager:
    return UseCaseManager(
        apps=[
            UseCaseAppConfig(
                name="project",
                description="project app",
                services=[ContextService],
                context_extractor=lambda ctx: {"user_id": ctx.get("user_id", 0)},
            ),
        ],
    )


# ──────────────────────────────────────────────────
# Happy path
# ──────────────────────────────────────────────────


class TestComposeHappyPath:
    @pytest.mark.asyncio
    async def test_single_service_single_method(self):
        app = _make_manager().get_app("project")
        result = await compose_and_resolve(
            app,
            "{ SprintService { list_sprints { id name } } }",
        )
        assert list(result.keys()) == ["SprintService"]
        assert list(result["SprintService"].keys()) == ["list_sprints"]
        sprints = result["SprintService"]["list_sprints"]
        assert len(sprints) == 2
        assert sprints[0] == {"id": 1, "name": "Sprint A"}

    @pytest.mark.asyncio
    async def test_single_service_multiple_methods(self):
        app = _make_manager().get_app("project")
        result = await compose_and_resolve(
            app,
            "{ SprintService { list_sprints { id } get_sprint(sprint_id: 1) { name } } }",
        )
        svc = result["SprintService"]
        assert len(svc["list_sprints"]) == 2
        assert svc["get_sprint"] == {"name": "Sprint A"}

    @pytest.mark.asyncio
    async def test_multiple_services_parallel(self):
        app = _make_manager().get_app("project")
        result = await compose_and_resolve(
            app,
            """
            {
              SprintService { list_sprints { id } }
              TaskService { list_tasks { id title } }
            }
            """,
        )
        assert set(result.keys()) == {"SprintService", "TaskService"}
        assert len(result["TaskService"]["list_tasks"]) == 2

    @pytest.mark.asyncio
    async def test_method_with_argument_int_coercion(self):
        app = _make_manager().get_app("project")
        result = await compose_and_resolve(
            app,
            "{ TaskService { get_task(task_id: 42) { id title } } }",
        )
        assert result["TaskService"]["get_task"] == {"id": 42, "title": "Task 42"}

    @pytest.mark.asyncio
    async def test_optional_argument_with_default_omitted(self):
        app = _make_manager().get_app("project")
        # include_owner has default=True; omit it.
        result = await compose_and_resolve(
            app,
            "{ TaskService { get_task(task_id: 1) { id } } }",
        )
        assert result["TaskService"]["get_task"]["id"] == 1

    @pytest.mark.asyncio
    async def test_list_return_with_projection(self):
        app = _make_manager().get_app("project")
        result = await compose_and_resolve(
            app,
            "{ SprintService { list_sprints { id name } } }",
        )
        sprints = result["SprintService"]["list_sprints"]
        assert all(set(s.keys()) == {"id", "name"} for s in sprints)

    @pytest.mark.asyncio
    async def test_optional_dto_returning_none(self):
        app = _make_manager().get_app("project")
        result = await compose_and_resolve(
            app,
            "{ SprintService { get_sprint(sprint_id: 999) { name } } }",
        )
        assert result["SprintService"]["get_sprint"] is None

    @pytest.mark.asyncio
    async def test_resolver_runs_on_dto_resolve_method(self):
        """DTO.resolve_owner should fire during Resolver phase, then be projected."""
        app = _make_manager().get_app("project")
        result = await compose_and_resolve(
            app,
            "{ TaskService { get_task(task_id: 1) { id owner { id name } } } }",
        )
        task = result["TaskService"]["get_task"]
        assert task["owner"] == {"id": 1, "name": "User1"}

    @pytest.mark.asyncio
    async def test_mutation_allowed_when_enabled(self):
        app = _make_manager(enable_mutation=True).get_app("project")
        result = await compose_and_resolve(
            app,
            '{ TaskService { create_task(title: "New") { id title } } }',
        )
        assert result["TaskService"]["create_task"]["title"] == "New"

    @pytest.mark.asyncio
    async def test_from_context_param_injection(self):
        app = _make_context_manager().get_app("project")
        result = await compose_and_resolve(
            app,
            "{ ContextService { get_my_tasks { id title } } }",
            context={"user_id": 7},
        )
        tasks = result["ContextService"]["get_my_tasks"]
        assert all("Task of 7" in t["title"] for t in tasks)


# ──────────────────────────────────────────────────
# Validation errors
# ──────────────────────────────────────────────────


class TestComposeValidation:
    @pytest.mark.asyncio
    async def test_empty_query(self):
        app = _make_manager().get_app("project")
        with pytest.raises(ComposeError, match="Query is empty"):
            await compose_and_resolve(app, "")

    @pytest.mark.asyncio
    async def test_syntax_error(self):
        app = _make_manager().get_app("project")
        with pytest.raises(ComposeError, match="GraphQL syntax error"):
            await compose_and_resolve(app, "{ SprintService ")

    @pytest.mark.asyncio
    async def test_alias_rejected(self):
        app = _make_manager().get_app("project")
        with pytest.raises(ComposeError, match="alias"):
            await compose_and_resolve(
                app,
                "{ s1: SprintService { list_sprints { id } } }",
            )

    @pytest.mark.asyncio
    async def test_unknown_service(self):
        app = _make_manager().get_app("project")
        with pytest.raises(ComposeError, match="Service 'NoSuchService'"):
            await compose_and_resolve(
                app,
                "{ NoSuchService { anything { id } } }",
            )

    @pytest.mark.asyncio
    async def test_unknown_method(self):
        app = _make_manager().get_app("project")
        with pytest.raises(ComposeError, match="Method 'no_such_method'"):
            await compose_and_resolve(
                app,
                "{ SprintService { no_such_method { id } } }",
            )

    @pytest.mark.asyncio
    async def test_missing_required_argument(self):
        app = _make_manager().get_app("project")
        with pytest.raises(ComposeError, match="Missing required argument 'sprint_id'"):
            await compose_and_resolve(
                app,
                "{ SprintService { get_sprint { name } } }",
            )

    @pytest.mark.asyncio
    async def test_unexpected_argument(self):
        app = _make_manager().get_app("project")
        with pytest.raises(ComposeError, match="Unexpected argument 'foobar'"):
            await compose_and_resolve(
                app,
                "{ SprintService { get_sprint(sprint_id: 1, foobar: 2) { name } } }",
            )

    @pytest.mark.asyncio
    async def test_argument_type_coercion_failure(self):
        app = _make_manager().get_app("project")
        with pytest.raises(ComposeError, match="Failed to coerce argument 'sprint_id'"):
            await compose_and_resolve(
                app,
                '{ SprintService { get_sprint(sprint_id: "not-an-int") { name } } }',
            )

    @pytest.mark.asyncio
    async def test_mutation_when_disabled(self):
        app = _make_manager(enable_mutation=False).get_app("project")
        with pytest.raises(ComposeError, match="mutations are disabled"):
            await compose_and_resolve(
                app,
                '{ TaskService { create_task(title: "x") { id } } }',
            )

    @pytest.mark.asyncio
    async def test_dto_method_requires_selection(self):
        app = _make_manager().get_app("project")
        with pytest.raises(ComposeError, match="requires field selection"):
            await compose_and_resolve(
                app,
                "{ SprintService { get_sprint(sprint_id: 1) } }",
            )

    @pytest.mark.asyncio
    async def test_dto_leaf_arguments_rejected(self):
        app = _make_manager().get_app("project")
        with pytest.raises(ComposeError, match="Arguments are not allowed on DTO field"):
            await compose_and_resolve(
                app,
                "{ TaskService { get_task(task_id: 1) { owner(limit: 5) { id } } } }",
            )

    @pytest.mark.asyncio
    async def test_service_level_arguments_rejected(self):
        app = _make_manager().get_app("project")
        with pytest.raises(ComposeError, match="not allowed on Service"):
            await compose_and_resolve(
                app,
                "{ SprintService(limit: 5) { list_sprints { id } } }",
            )

    @pytest.mark.asyncio
    async def test_unknown_field_in_selection(self):
        app = _make_manager().get_app("project")
        with pytest.raises(ComposeError, match="Unknown field"):
            await compose_and_resolve(
                app,
                "{ SprintService { list_sprints { nonexistent } } }",
            )

    @pytest.mark.asyncio
    async def test_sub_selection_on_scalar_rejected(self):
        app = _make_manager().get_app("project")
        with pytest.raises(ComposeError):
            await compose_and_resolve(
                app,
                "{ SprintService { list_sprints { id { foo } } } }",
            )


# ──────────────────────────────────────────────────
# MCP integration
# ──────────────────────────────────────────────────


@pytest.fixture
def mcp_server():
    return create_use_case_mcp_server(
        apps=[
            UseCaseAppConfig(
                name="project",
                description="Project management",
                services=[SprintService, TaskService],
            ),
        ],
        name="Compose Test API",
    )


class TestComposeMcpTool:
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
        assert data["data"]["SprintService"]["list_sprints"][0]["name"] == "Sprint A"

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
            {"app_name": "no_such_app", "query": "{ SprintService { list_sprints { id } } }"},
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is False
        assert data["error_type"] == "app_not_found"
