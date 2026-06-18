"""UseCase GraphQL MCP Server — 4-layer progressive disclosure.

A standalone MCP server (independent from ``server.create_use_case_mcp_server``)
that exposes the compose surface via four tools mirroring the classic
server's progressive-disclosure pattern:

- ``list_apps`` — Layer 1: cheap app discovery (names + service counts).
- ``describe_compose_schema`` — Layer 2: per-app service + method
  listing (names, kinds, descriptions only). Compact — does NOT include
  args, return types, or DTO fields.
- ``describe_compose_method`` — Layer 3: per-method detail (args with
  types/defaults, return type, top-level DTO fields). Nested DTO fields
  are marked ``nested=true`` but not expanded — their field lists are
  discovered via error recovery in Layer 4 (the ``Unknown field.
  Available fields: [...]`` message from ``build_subset_model``).
- ``compose_query`` — Layer 4: execute a GraphQL data query against the
  compose surface (3-level hierarchy: Service → Method → DTO field
  selection). Pure data — introspection queries (``__schema`` /
  ``__type`` / ``__typename``) are rejected with a hint pointing back to
  Layer 2.

The two servers are intentionally separate. The classic server follows
the progressive-disclosure + flat-parameter MCP style; this one follows
the GraphQL-string style. Each is self-contained: their docstrings and
hints do not cross-reference the other server's tools.

See ``demo/use_case/mcp_server_compose.py`` for a runnable example.
"""

from __future__ import annotations

import inspect
import re
from typing import TYPE_CHECKING, Annotated, Any, get_args, get_origin

from fastmcp.server.context import Context

from pydantic_resolve.graphql.mcp.types.errors import (
    MCPErrors,
    create_error_response,
    create_success_response,
)
from pydantic_resolve.use_case.business import USE_CASE_METHODS_ATTR
from pydantic_resolve.use_case.compose import (
    ComposeError,
    compose_and_resolve,
    is_introspection_query,
)
from pydantic_resolve.use_case.context import FromContext
from pydantic_resolve.use_case.manager import UseCaseManager
from pydantic_resolve.use_case.selection import _get_pydantic_core_type
from pydantic_resolve.use_case.server import _extract_context
from pydantic_resolve.use_case.types import UseCaseAppConfig
from pydantic_resolve.utils.types import _resolve_function_type_hints, get_return_annotation

if TYPE_CHECKING:
    from fastmcp import FastMCP


def create_use_case_graphql_mcp_server(
    apps: list[UseCaseAppConfig],
    name: str = "Pydantic-Resolve UseCase GraphQL API",
) -> "FastMCP":
    """Create an MCP server with 4-layer progressive disclosure.

    Independent from ``create_use_case_mcp_server`` (the classic
    progressive-disclosure server). ``describe_compose_schema``,
    ``describe_compose_method``, and ``compose_query`` take ``app_name``
    to target a specific app in ``apps``; ``list_apps`` returns the list
    of valid app names.

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

    # Layer 1: cheap app discovery
    @mcp.tool()
    def list_apps() -> dict[str, Any]:
        """List all available UseCase applications.

        Returns a list of all configured applications with their metadata:
        - name: Application name
        - description: Application description
        - services_count: Number of services in the app

        IMPORTANT: All subsequent tool calls require the ``app_name``
        parameter. Choose an app_name from this list.

        Returns:
            Dictionary with ``success``, ``data`` (list of app metadata),
            and a ``hint`` pointing to ``describe_compose_schema``.
        """
        try:
            apps_info = [
                {
                    "name": app.name,
                    "description": app.description,
                    "services_count": len(app.services),
                }
                for app in manager.apps.values()
            ]
            app_names = [a["name"] for a in apps_info]
            first = app_names[0] if app_names else "app_name"
            return {
                "success": True,
                "data": apps_info,
                "hint": (
                    f"Use describe_compose_schema(app_name='{first}') to list "
                    f"services and methods for an app. Available apps: {app_names}."
                ),
            }
        except Exception as e:
            return create_error_response(str(e), MCPErrors.INTERNAL_ERROR)

    # Layer 2: per-app service + method listing (cheap overview)
    @mcp.tool()
    def describe_compose_schema(app_name: str) -> dict[str, Any]:
        """List services and methods for an app.

        Returns each service's name + description and its ``@query`` /
        ``@mutation`` method names + kinds + descriptions. Intentionally
        does NOT include method args, return types, or DTO fields — to
        keep the response compact. Use ``describe_compose_method`` for
        any method whose args / return shape you need.

        Mutations are filtered out when the app has ``enable_mutation=False``.

        Args:
            app_name: Name of the application (from ``list_apps``).

        Returns:
            Dictionary with ``success``, ``data`` (nested
            ``{service: {methods: [{name, kind, description}]}}``), and
            a ``hint`` pointing to ``describe_compose_method``. On
            failure: ``success=False``, ``error``, ``error_type``.
        """
        try:
            app = manager.get_app(app_name)
        except ValueError:
            return create_error_response(
                f"App '{app_name}' not found. Available apps: "
                f"{list(manager.apps.keys())}.",
                MCPErrors.APP_NOT_FOUND,
            )

        services: dict[str, Any] = {}
        for svc_name, svc_cls in app.services.items():
            methods_meta = getattr(svc_cls, USE_CASE_METHODS_ATTR, {})
            method_list: list[dict[str, Any]] = []
            for m_name, meta in methods_meta.items():
                kind = meta.get("kind", "query") if isinstance(meta, dict) else "query"
                if kind == "mutation" and not app.enable_mutation:
                    continue
                method_list.append(
                    {
                        "name": m_name,
                        "kind": kind,
                        "description": (
                            meta.get("description") if isinstance(meta, dict) else None
                        ),
                    }
                )
            services[svc_name] = {
                "description": (svc_cls.__doc__ or None),
                "methods": method_list,
            }

        first_svc = next(iter(services.keys()), "ServiceName")
        first_method = (
            services[first_svc]["methods"][0]["name"]
            if services.get(first_svc, {}).get("methods")
            else "method_name"
        )
        return {
            "success": True,
            "data": {"services": services},
            "hint": (
                f"Use describe_compose_method(app_name='{app_name}', "
                f"service_name='{first_svc}', method_name='{first_method}') "
                f"to inspect args / return type / DTO fields for a method."
            ),
        }

    # Layer 3: per-method detail (args, returns, DTO fields)
    @mcp.tool()
    def describe_compose_method(
        app_name: str, service_name: str, method_name: str
    ) -> dict[str, Any]:
        """Get detailed info for a single method.

        Returns the method's args (with types + defaults), return type,
        and (for DTO returns) the list of selectable top-level fields.
        Use this after ``describe_compose_schema`` to learn a specific
        method's signature before calling it via ``compose_query``.

        Nested DTO fields are marked ``nested=true`` but NOT expanded —
        if you select a nested field with the wrong sub-field, the
        ``compose_query`` error response will list the available fields
        for that DTO.

        Args:
            app_name: Name of the application (from ``list_apps``).
            service_name: Name of the service (from ``describe_compose_schema``).
            method_name: Name of the method (from ``describe_compose_schema``).

        Returns:
            Dictionary with ``success``, ``data`` (method detail), and
            a ``hint`` pointing to ``compose_query``. On failure:
            ``success=False``, ``error``, ``error_type``.
        """
        try:
            app = manager.get_app(app_name)
        except ValueError:
            return create_error_response(
                f"App '{app_name}' not found. Available apps: "
                f"{list(manager.apps.keys())}.",
                MCPErrors.APP_NOT_FOUND,
            )

        service_cls = app.services.get(service_name)
        if service_cls is None:
            return create_error_response(
                f"Service '{service_name}' not found in app '{app_name}'. "
                f"Available services: {list(app.services.keys())}.",
                MCPErrors.TYPE_NOT_FOUND,
            )

        methods_meta = getattr(service_cls, USE_CASE_METHODS_ATTR, {})
        meta = methods_meta.get(method_name)
        if meta is None:
            return create_error_response(
                f"Method '{method_name}' not found in service '{service_name}'. "
                f"Available methods: {list(methods_meta.keys())}.",
                MCPErrors.OPERATION_NOT_FOUND,
            )

        kind = meta.get("kind", "query") if isinstance(meta, dict) else "query"
        if kind == "mutation" and not app.enable_mutation:
            return create_error_response(
                f"Method '{method_name}' is a mutation and mutations are "
                f"disabled for app '{app_name}'.",
                MCPErrors.OPERATION_NOT_FOUND,
            )

        method = meta["method"]
        func = getattr(method, "__func__", method)
        return_anno = get_return_annotation(method)
        core_type = _get_pydantic_core_type(return_anno)

        method_info: dict[str, Any] = {
            "name": method_name,
            "kind": kind,
            "description": (
                meta.get("description") if isinstance(meta, dict) else None
            ),
            "args": _build_args_info(func),
            "returns": _python_type_to_str(return_anno),
        }
        if core_type is not None:
            method_info["fields"] = _dto_fields_info(core_type)

        return {
            "success": True,
            "data": method_info,
            "hint": (
                f"Use compose_query(app_name='{app_name}', "
                f"query='{{ {service_name} {{ {method_name} {{ field }} }} }}') "
                f"to execute."
            ),
        }

    # Layer 3: data query execution
    @mcp.tool()
    async def compose_query(
        app_name: str,
        query: str,
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict[str, Any]:
        """Compose multiple UseCaseService methods in a single GraphQL query.

        Fixed 3-level hierarchy: Query root → Service → Method → DTO field
        selection. Useful for fetching related data across services in one
        round trip.

        Rules:
        - No aliases (GraphQL ``field:`` syntax). Each field name must be
          unique within its parent.
        - Service / method names must match the schema. Use
          ``describe_compose_schema`` to discover valid names.
        - Method arguments go in parentheses on the method field:
          ``get_sprint(sprint_id: 1)``.
        - Parameters marked ``FromContext`` (server-injected: auth user,
          tenant, etc.) CANNOT be set from query arguments.
        - DTO field selection under each method projects into that
          method's return DTO. Nested DTOs require sub-selection; if you
          pick a wrong sub-field, the error response lists the available
          fields for that DTO.
        - Mutations require the app to have ``enable_mutation=True``.
        - Introspection queries (``__schema`` / ``__type`` /
          ``__typename``) are rejected — use ``describe_compose_schema``
          for schema discovery instead.

        Execution semantics:
        - ``@query`` methods run concurrently.
        - ``@mutation`` methods run serially in declaration order.
        - The relative ordering between queries and mutations within a
          single compose call is NOT guaranteed. If you need
          create-then-read semantics, issue them as separate
          ``compose_query`` calls.

        The response shape mirrors the request: each Service becomes a
        key whose value is a dict of method-name → result.

        Args:
            app_name: Application name (from ``list_apps``).
            query: GraphQL data query string (introspection is rejected).
            ctx: MCP request context (used for context_extractor).

        Returns:
            ``{success, data: {service: {method: result}}, hint}`` on
            success. On failure: ``success=False``, ``error``,
            ``error_type`` (one of: validation_error, type_not_found,
            operation_not_found, query_execution_error,
            mutation_execution_error, app_not_found, internal_error).

        Example::

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
        if is_introspection_query(query):
            return create_error_response(
                "GraphQL introspection is not available via compose_query. "
                "Use describe_compose_schema(app_name=...) to discover "
                "available services, methods, and DTO fields.",
                MCPErrors.VALIDATION_ERROR,
            )

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
                f"Composed query executed for app '{app_name}'. "
                f"To compose another query, reuse the same syntax."
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


def _build_args_info(func: Any) -> list[dict[str, Any]]:
    """Compact arg info list for a method's signature.

    Skips ``cls`` and ``FromContext`` params (same rule as
    ``compose_schema._build_method_args``).
    """
    sig = inspect.signature(func)
    hints = _resolve_function_type_hints(func)
    args_info: list[dict[str, Any]] = []
    for name, param in sig.parameters.items():
        if name == "cls":
            continue
        anno = hints.get(name, param.annotation)
        if _is_from_context_param(anno):
            continue
        info: dict[str, Any] = {
            "name": name,
            "type": _python_type_to_str(anno),
        }
        if param.default is not inspect.Parameter.empty:
            info["default"] = param.default
        args_info.append(info)
    return args_info


def _is_from_context_param(annotation: Any) -> bool:
    if annotation is None or annotation is inspect.Parameter.empty:
        return False
    if get_origin(annotation) is not Annotated:
        return False
    return any(isinstance(arg, FromContext) for arg in get_args(annotation))


def _python_type_to_str(anno: Any) -> str:
    """Compact Python type string for LLM consumption.

    - ``int`` / ``str`` / ``bool`` / ``float`` / builtins → bare name
    - Class references → ``ClassName`` (module prefix stripped)
    - ``typing.Optional[X]`` / ``Union[X, None]`` → preserved, inner classes cleaned
    - ``typing.List[X]`` / ``list[X]`` → preserved, inner classes cleaned
    """
    if anno is None or anno is inspect.Parameter.empty:
        return "Any"
    if isinstance(anno, type):
        return anno.__name__
    # typing constructs render like ``list[module.path.ClassName]`` —
    # strip ``typing.`` prefix and any module path before a Capitalized name.
    s = str(anno).replace("typing.", "")
    s = re.sub(r"\b[\w.]+\.([A-Z]\w*)", r"\1", s)
    return s


def _dto_fields_info(model_cls: type) -> list[dict[str, Any]]:
    """Compact field info for a Pydantic DTO.

    ``nested=True`` marks fields whose type is itself a Pydantic model
    (so they require sub-selection in the compose query). Nested DTOs
    are NOT recursively expanded — their field lists are discovered via
    error recovery in ``compose_query`` (``Unknown field. Available
    fields: [...]``).
    """
    fields: list[dict[str, Any]] = []
    for name, field_info in model_cls.model_fields.items():
        anno = field_info.annotation
        core = _get_pydantic_core_type(anno)
        fields.append(
            {
                "name": name,
                "type": _python_type_to_str(anno),
                "nested": core is not None,
            }
        )
    return fields


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
