"""Tests for compose_query introspection (``__schema`` / ``__type`` / ``__typename``).

Covers:
- Schema completeness (services, methods, args, DTO fields)
- Type system (Optional, list, Enum, recursion, shared DTOs)
- Mutation control
- Entry routing (Python auto-route, MCP rejection, partial introspection)
- GraphiQL canonical introspection query
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Optional

import pytest
from pydantic import BaseModel

from pydantic_resolve import query, mutation
from pydantic_resolve.use_case.business import UseCaseService
from pydantic_resolve.use_case.compose import ComposeError
from pydantic_resolve.use_case.introspection import (
    compose_introspect,
    is_introspection_query,
)
from pydantic_resolve.use_case.manager import UseCaseManager
from pydantic_resolve.use_case.mcp_server import (
    create_use_case_graphql_mcp_server,
)
from pydantic_resolve.use_case.manager import UseCaseAppConfig


# ──────────────────────────────────────────────────
# DTOs
# ──────────────────────────────────────────────────


class Color(Enum):
    RED = "red"
    GREEN = "green"


class OwnerDTO(BaseModel):
    id: int
    name: str


class TaskDTO(BaseModel):
    id: int
    title: str
    owner_id: int
    color: Color
    owner: Optional[OwnerDTO] = None
    subtasks: list["TaskDTO"] = []

    def resolve_owner(self):
        return OwnerDTO(id=self.owner_id, name=f"User{self.owner_id}")


TaskDTO.model_rebuild()


class SprintDTO(BaseModel):
    id: int
    name: str


# ──────────────────────────────────────────────────
# Services
# ──────────────────────────────────────────────────


class SprintService(UseCaseService):
    """Sprint service."""

    @query
    async def list_sprints(cls) -> list[SprintDTO]:
        return [SprintDTO(id=1, name="A"), SprintDTO(id=2, name="B")]

    @query
    async def get_sprint(cls, sprint_id: int) -> Optional[SprintDTO]:
        return SprintDTO(id=sprint_id, name="X") if sprint_id == 1 else None


class TaskService(UseCaseService):
    """Task service."""

    @query
    async def list_tasks(cls, limit: int = 10) -> list[TaskDTO]:
        return [TaskDTO(id=1, title="t", owner_id=1, color=Color.RED)]

    @query
    async def get_task(cls, task_id: int) -> TaskDTO:
        return TaskDTO(id=task_id, title="t", owner_id=1, color=Color.RED)

    @mutation
    async def create_task(cls, title: str) -> TaskDTO:
        return TaskDTO(id=99, title=title, owner_id=1, color=Color.RED)


# ──────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────


def _make_manager(*, enable_mutation: bool = True) -> UseCaseManager:
    return UseCaseManager(
        apps=[
            UseCaseAppConfig(
                name="project",
                description="project",
                services=[SprintService, TaskService],
                enable_mutation=enable_mutation,
            ),
        ],
    )


def _introspect_types(app) -> dict[str, dict]:
    """Return {type_name: type_def} for all types in the schema."""
    result = compose_introspect(app)
    return {t["name"]: t for t in result["data"]["__schema"]["types"]}


# ──────────────────────────────────────────────────
# is_introspection_query
# ──────────────────────────────────────────────────


class TestIsIntrospectionQuery:
    def test_detects_schema(self):
        assert is_introspection_query("{ __schema { types { name } } }")

    def test_detects_type(self):
        assert is_introspection_query('{ __type(name: "X") { name } }')

    def test_detects_typename(self):
        assert is_introspection_query("{ __typename }")

    def test_rejects_normal_query(self):
        assert not is_introspection_query("{ SprintService { list_sprints { id } } }")

    def test_rejects_empty(self):
        assert not is_introspection_query("")


# ──────────────────────────────────────────────────
# Schema completeness
# ──────────────────────────────────────────────────


class TestSchemaCompleteness:
    def test_returns_graphql_envelope(self):
        app = _make_manager().get_app("project")
        result = compose_introspect(app)
        assert set(result.keys()) == {"data", "errors"}
        assert result["errors"] is None
        assert "__schema" in result["data"]

    def test_query_type_has_all_services_as_fields(self):
        app = _make_manager().get_app("project")
        types = _introspect_types(app)
        query_type = types["Query"]
        field_names = {f["name"] for f in query_type["fields"]}
        assert field_names >= {"SprintService", "TaskService"}

    def test_query_type_service_fields_reference_service_query_objects(self):
        """Each root-Query service field must point at its ``{Service}Query``
        OBJECT, not regress to a scalar fallback (UseCaseService subclasses
        aren't BaseModels, so TypeMapper alone can't map them)."""
        app = _make_manager().get_app("project")
        types = _introspect_types(app)
        query_type = types["Query"]
        by_name = {f["name"]: f for f in query_type["fields"]}
        # SprintService: SprintServiceQuery! → NON_NULL(OBJECT(SprintServiceQuery))
        sprint = by_name["SprintService"]["type"]
        assert sprint["kind"] == "NON_NULL"
        assert sprint["ofType"]["kind"] == "OBJECT"
        assert sprint["ofType"]["name"] == "SprintServiceQuery"
        task = by_name["TaskService"]["type"]
        assert task["kind"] == "NON_NULL"
        assert task["ofType"]["name"] == "TaskServiceQuery"

    def test_service_object_type_has_methods(self):
        app = _make_manager().get_app("project")
        types = _introspect_types(app)
        sprint_q = types["SprintServiceQuery"]
        method_names = {f["name"] for f in sprint_q["fields"]}
        assert method_names >= {"list_sprints", "get_sprint"}

    def test_method_args_appear_with_correct_types(self):
        app = _make_manager().get_app("project")
        # __type lookup focusing on the args
        result = compose_introspect(
            app,
            '{ __type(name: "SprintServiceQuery") '
            "{ fields { name args { name type { kind name ofType { kind name } } } } } }",
        )
        fields = result["data"]["__type"]["fields"]
        get_sprint = next(f for f in fields if f["name"] == "get_sprint")
        assert get_sprint["args"][0]["name"] == "sprint_id"
        # sprint_id: int (non-null) → NON_NULL Int
        t = get_sprint["args"][0]["type"]
        assert t["kind"] == "NON_NULL"
        assert t["ofType"]["name"] == "Int"

    def test_optional_arg_becomes_nullable(self):
        app = _make_manager().get_app("project")
        result = compose_introspect(
            app,
            '{ __type(name: "TaskServiceQuery") '
            "{ fields { name args { name type { kind name ofType { kind name } } } } } }",
        )
        fields = result["data"]["__type"]["fields"]
        list_tasks = next(f for f in fields if f["name"] == "list_tasks")
        # limit: int = 10 → nullable Int (has default → strip NonNull)
        limit_arg = next(a for a in list_tasks["args"] if a["name"] == "limit")
        assert limit_arg["type"]["kind"] == "SCALAR"
        assert limit_arg["type"]["name"] == "Int"

    def test_arg_default_value_is_graphql_literal(self):
        """``defaultValue`` must be a GraphQL literal, not Python repr.

        GraphQL spec wants ``true`` / ``false`` (lowercase) and
        double-quoted strings. Python repr gives ``True`` / ``'hi'``
        which GraphiQL would reject. Regression for the ``repr()``
        → ``json.dumps()`` fix.
        """
        from pydantic_resolve.use_case.compose_schema import _build_method_args

        class Probe:
            @classmethod
            async def m(
                cls,
                a: int = 42,
                b: str = "hi",
                c: bool = True,
                d: bool = False,
                e: list[int] = [1, 2],
            ):
                ...

        args = {a.name: a for a in _build_method_args(Probe.m.__func__)}
        assert args["a"].default_value == "42"          # int — repr and json match
        assert args["b"].default_value == '"hi"'        # str — JSON double-quoted, not repr's 'hi'
        assert args["c"].default_value == "true"        # bool True → lowercase true
        assert args["d"].default_value == "false"       # bool False → lowercase false
        assert args["e"].default_value == "[1, 2]"      # list → JSON array

    def test_dto_fields_appear(self):
        app = _make_manager().get_app("project")
        result = compose_introspect(
            app,
            '{ __type(name: "TaskDTO") { fields { name type { kind name ofType { kind name } } } } }',
        )
        fields = {f["name"]: f for f in result["data"]["__type"]["fields"]}
        assert "id" in fields
        assert "title" in fields
        # id: int → NON_NULL Int
        assert fields["id"]["type"]["kind"] == "NON_NULL"
        assert fields["id"]["type"]["ofType"]["name"] == "Int"
        # owner: Optional[OwnerDTO] → nullable OBJECT
        assert fields["owner"]["type"]["kind"] == "OBJECT"
        assert fields["owner"]["type"]["name"] == "OwnerDTO"


# ──────────────────────────────────────────────────
# Type system
# ──────────────────────────────────────────────────


class TestTypeSystem:
    def test_list_type_is_non_null_list(self):
        app = _make_manager().get_app("project")
        result = compose_introspect(
            app,
            '{ __type(name: "SprintServiceQuery") '
            "{ fields { name type { kind ofType { kind ofType { kind ofType { kind name } } } } } } }",
        )
        fields = result["data"]["__type"]["fields"]
        list_sprints = next(f for f in fields if f["name"] == "list_sprints")
        # list[SprintDTO] → NON_NULL LIST NON_NULL SprintDTO
        t = list_sprints["type"]
        assert t["kind"] == "NON_NULL"
        assert t["ofType"]["kind"] == "LIST"
        assert t["ofType"]["ofType"]["kind"] == "NON_NULL"
        assert t["ofType"]["ofType"]["ofType"]["name"] == "SprintDTO"

    def test_enum_type_supported(self):
        app = _make_manager().get_app("project")
        types = _introspect_types(app)
        assert "Color" in types
        assert types["Color"]["kind"] == "ENUM"
        values = {v["name"] for v in types["Color"]["enumValues"]}
        assert values == {"RED", "GREEN"}

    def test_recursive_dto_does_not_infinite_loop(self):
        app = _make_manager().get_app("project")
        # TaskDTO has subtasks: list[TaskDTO] — must not loop forever.
        types = _introspect_types(app)
        assert "TaskDTO" in types

    def test_shared_dto_appears_once(self):
        app = _make_manager().get_app("project")
        # Both SprintService.list_sprints and TaskService.get_task reference DTOs.
        types = _introspect_types(app)
        # OwnerDTO referenced by TaskDTO.owner; SprintDTO by list_sprints — each appears once.
        assert list(types.keys()).count("OwnerDTO") == 1
        assert list(types.keys()).count("SprintDTO") == 1


# ──────────────────────────────────────────────────
# Mutation control
# ──────────────────────────────────────────────────


class TestMutationControl:
    def test_mutation_excluded_when_disabled(self):
        app = _make_manager(enable_mutation=False).get_app("project")
        result = compose_introspect(
            app,
            '{ __type(name: "TaskServiceQuery") { fields { name } } }',
        )
        names = {f["name"] for f in result["data"]["__type"]["fields"]}
        assert "create_task" not in names
        assert "get_task" in names

    def test_mutation_included_when_enabled(self):
        app = _make_manager(enable_mutation=True).get_app("project")
        result = compose_introspect(
            app,
            '{ __type(name: "TaskServiceQuery") { fields { name } } }',
        )
        names = {f["name"] for f in result["data"]["__type"]["fields"]}
        assert "create_task" in names


# ──────────────────────────────────────────────────
# Entry routing
# ──────────────────────────────────────────────────


class TestEntryRouting:
    @pytest.mark.asyncio
    async def test_introspection_query_no_longer_auto_routed(self):
        """Introspection queries must NOT be handled by ``app.compose``.
        Passing one now surfaces as type_not_found — callers must dispatch
        to compose_introspect themselves via is_introspection_query."""
        app = _make_manager().get_app("project")
        with pytest.raises(ComposeError) as exc_info:
            await app.compose("{ __schema { queryType { name } } }")
        assert exc_info.value.error_type == "type_not_found"
        # __schema is parsed as a service name, which doesn't exist
        assert "__schema" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_data_query_still_works_via_compose(self):
        """Sanity check: removing the auto-route doesn't break data queries."""
        app = _make_manager().get_app("project")
        result = await app.compose("{ SprintService { list_sprints { id name } } }")
        assert "SprintService" in result

    def test_compose_introspect_explicit_call_returns_envelope(self):
        app = _make_manager().get_app("project")
        result = compose_introspect(app)
        assert result["data"]["__schema"]["queryType"]["name"] == "Query"

    def test_partial_introspection_query_supported(self):
        app = _make_manager().get_app("project")
        result = compose_introspect(
            app, '{ __type(name: "SprintDTO") { name fields { name } } }'
        )
        assert result["data"]["__type"]["name"] == "SprintDTO"
        field_names = {f["name"] for f in result["data"]["__type"]["fields"]}
        assert field_names == {"id", "name"}

    def test_typename_query(self):
        app = _make_manager().get_app("project")
        result = compose_introspect(app, "{ __typename }")
        assert result["data"]["__typename"] == "Query"

    @pytest.mark.asyncio
    async def test_mcp_tool_rejects_introspection_with_hint(self):
        """Layer 3 (compose_query) rejects GraphQL introspection and
        redirects to Layer 2 (describe_compose_schema). Schema discovery
        belongs to Layer 2; Layer 3 owns execution only.
        """
        mcp = create_use_case_graphql_mcp_server(
            apps=[
                UseCaseAppConfig(
                    name="project",
                    description="p",
                    services=[SprintService, TaskService],
                ),
            ],
        )
        result = await mcp.call_tool(
            "compose_query",
            {"app_name": "project", "query": "{ __schema { types { name } } }"},
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is False
        assert "describe_compose_schema" in data["error"]
        assert data["error_type"] == "validation_error"


# ──────────────────────────────────────────────────
# GraphiQL compatibility
# ──────────────────────────────────────────────────


class TestGraphiQLCompatibility:
    def test_canonical_graphiql_introspection_query_works(self):
        """The exact query GraphiQL sends on boot must succeed."""
        app = _make_manager().get_app("project")
        canonical = """
        query IntrospectionQuery {
          __schema {
            queryType { name }
            mutationType { name }
            subscriptionType { name }
            types { ...FullType }
            directives {
              name
              description
              locations
              args { ...InputValue }
            }
          }
        }
        fragment FullType on __Type {
          kind
          name
          description
          fields(includeDeprecated: true) {
            name
            description
            args { ...InputValue }
            type { ...TypeRef }
            isDeprecated
            deprecationReason
          }
          inputFields { ...InputValue }
          interfaces { ...TypeRef }
          enumValues(includeDeprecated: true) {
            name
            description
            isDeprecated
            deprecationReason
          }
          possibleTypes { ...TypeRef }
        }
        fragment InputValue on __InputValue {
          name
          description
          type { ...TypeRef }
          defaultValue
        }
        fragment TypeRef on __Type {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
                ofType {
                  kind
                  name
                  ofType {
                    kind
                    name
                    ofType {
                      kind
                      name
                      ofType { kind name }
                    }
                  }
                }
              }
            }
          }
        }
        """
        result = compose_introspect(app, canonical)
        assert result["errors"] is None
        schema = result["data"]["__schema"]
        assert schema["queryType"]["name"] == "Query"
        # mutationType is None in compose (no mutation root)
        assert schema["mutationType"] is None
        # Standard GraphQL directives must be present.
        directive_names = {d["name"] for d in schema["directives"]}
        assert {"skip", "include", "deprecated", "oneOf"} <= directive_names
