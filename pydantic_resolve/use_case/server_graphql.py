"""UseCase GraphQL MCP Server — single-entry compose query surface.

A standalone MCP server (independent from ``server.create_use_case_mcp_server``)
that exposes the compose surface via a single tool:

- ``compose_query`` — execute a GraphQL query against the compose schema.
  Supports both data queries (3-level hierarchy: Service → Method → DTO
  field selection) and standard GraphQL introspection (``__schema`` /
  ``__type`` / ``__typename``) for schema discovery.

The two servers are intentionally separate. The classic server follows
the progressive-disclosure + flat-parameter MCP style; this one follows
the GraphQL-string style. Each is self-contained: their docstrings and
hints do not cross-reference the other server's tools.

See ``demo/use_case/mcp_server_compose.py`` for a runnable example.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastmcp.server.context import Context

from pydantic_resolve.graphql.mcp.types.errors import (
    MCPErrors,
    create_error_response,
    create_success_response,
)
from pydantic_resolve.use_case.compose import (
    ComposeError,
    compose_and_resolve,
)
from pydantic_resolve.use_case.manager import UseCaseManager
from pydantic_resolve.use_case.server import _extract_context
from pydantic_resolve.use_case.types import UseCaseAppConfig

if TYPE_CHECKING:
    from fastmcp import FastMCP


def create_use_case_graphql_mcp_server(
    apps: list[UseCaseAppConfig],
    name: str = "Pydantic-Resolve UseCase GraphQL API",
) -> "FastMCP":
    """Create an MCP server exposing ``compose_query``.

    Independent from ``create_use_case_mcp_server`` (the classic
    progressive-disclosure server). The tool takes ``app_name`` to
    target a specific app in ``apps``.

    Args:
        apps: List of ``UseCaseAppConfig`` (same shape as the classic server).
        name: MCP server name shown to clients.

    Returns:
        Configured ``FastMCP`` instance.
    """
    from fastmcp import FastMCP

    if not apps:
        raise ValueError("apps list cannot be empty")

    manager = UseCaseManager(apps)
    mcp = FastMCP(name)

    @mcp.tool()
    async def compose_query(
        app_name: str,
        query: str,
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict[str, Any]:
        """Compose multiple UseCaseService methods in a single GraphQL query.

        Two query modes share this entry point:

        **Data query** — fixed 3-level hierarchy: Query root → Service →
        Method → DTO field selection. Useful for fetching related data
        across services in one round trip.

        **Introspection query** — standard GraphQL ``__schema`` /
        ``__type(name: "...")`` / ``__typename``. Use this to discover
        available services, methods, arguments, and DTO field shapes
        (including nested DTOs) before composing a data query. Multi-layer
        progressive disclosure works natively: shallow queries return
        overviews, ``__type`` drills into one DTO at a time.

        Data query rules:
        - No aliases (GraphQL ``field:`` syntax). Each field name must be
          unique within its parent.
        - Service / method names must match the schema. Use
          ``{ __schema { queryType { fields { name } } } }`` to list
          services/methods, and ``{ __type(name: "X") { fields { name } } }``
          to inspect a DTO.
        - Method arguments go in parentheses on the method field:
          ``get_sprint(sprint_id: 1)``.
        - Parameters marked ``FromContext`` (server-injected: auth user,
          tenant, etc.) CANNOT be set from query arguments.
        - DTO field selection under each method projects into that
          method's return DTO. Nested DTOs require sub-selection.
        - Mutations require the app to have ``enable_mutation=True``.

        Execution semantics:
        - ``@query`` methods run concurrently.
        - ``@mutation`` methods run serially in declaration order.
        - The relative ordering between queries and mutations within a
          single compose call is NOT guaranteed. If you need
          create-then-read semantics, issue them as separate
          ``compose_query`` calls.

        The data-query response shape mirrors the request: each Service
        becomes a key whose value is a dict of method-name → result.
        The introspection-query response follows the standard GraphQL
        ``{data: {...}, errors: null}`` envelope.

        Args:
            app_name: Application name.
            query: GraphQL query string (data or introspection).
            ctx: MCP request context (used for context_extractor).

        Returns:
            ``{success, data, hint}`` on success. On failure:
            ``success=False``, ``error``, ``error_type`` (one of:
            validation_error, type_not_found, operation_not_found,
            query_execution_error, mutation_execution_error,
            app_not_found, internal_error).

        Example (introspection)::

            compose_query(
                app_name="project",
                query="{ __schema { queryType { fields { name } } } }",
            )
            compose_query(
                app_name="project",
                query='{ __type(name: "SprintDTO") { fields { name type { name kind ofType { name } } } } }',
            )

        Example (data query)::

            compose_query(
                app_name="project",
                query='''
                {
                  SprintService {
                    list_sprints { id name }
                    get_sprint(sprint_id: 1) { name }
                  }
                  TaskService {
                    get_task(task_id: 1) { title owner_id }
                  }
                }
                ''',
            )
        """
        try:
            app = manager.get_app(app_name)
        except ValueError:
            return create_error_response(
                f"App '{app_name}' not found. Available apps: "
                f"{list(manager.apps.keys())}.",
                MCPErrors.APP_NOT_FOUND,
            )

        try:
            context = await _extract_context(app, ctx)
            data = await compose_and_resolve(app, query, context=context)
            response = create_success_response(data)
            response["hint"] = (
                f"Query executed for app '{app_name}'. "
                f"Reuse the same syntax for further queries."
            )
            return response
        except ComposeError as e:
            error_enum = _compose_error_to_enum(e.error_type)
            return create_error_response(str(e), error_enum)
        except Exception as e:
            return create_error_response(
                f"Internal error while composing query: {e}",
                MCPErrors.INTERNAL_ERROR,
            )

    return mcp


# ============================================================================
# Helpers (local; intentionally not exported)
# ============================================================================


def _compose_error_to_enum(error_type: str) -> MCPErrors:
    """Map ComposeError.error_type string to an MCPErrors member.

    Falls back to VALIDATION_ERROR when the string does not match a known
    member — keeps the MCP response well-formed even if compose.py raises
    with a typo'd error_type.
    """
    for member in MCPErrors:
        if member.value == error_type:
            return member
    return MCPErrors.VALIDATION_ERROR


__all__ = ["create_use_case_graphql_mcp_server"]
