"""UseCase GraphQL MCP Server — 4-layer progressive disclosure.

The single MCP server factory for UseCase services. Exposes the
compose surface via four tools in a progressive-disclosure pattern:

- ``list_apps`` — Layer 1: cheap app discovery (names + service counts).
- ``describe_compose_schema`` — Layer 2: per-app service + method
  listing (names, kinds, descriptions only). Compact — does NOT include
  args, return types, or DTO fields.
- ``describe_compose_method`` — Layer 3: per-method detail (args with
  types/defaults, return type, and an ``sdl`` string showing the method
  signature + return DTO + every nested DTO reachable through its
  fields). The ``sdl`` is the source of truth for field info — top-level
  and nested alike.
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
from pydantic_resolve.use_case.types import UseCaseAppConfig
from pydantic_resolve.utils.types import _resolve_function_type_hints, get_return_annotation

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from pydantic_resolve.use_case.manager import UseCaseResources


def create_use_case_graphql_mcp_server(
    apps: list[UseCaseAppConfig],
    name: str = "Pydantic-Resolve UseCase GraphQL API",
) -> "FastMCP":
    """Create an MCP server with 4-layer progressive disclosure.

    ``describe_compose_schema``, ``describe_compose_method``, and
    ``compose_query`` take ``app_name`` to target a specific app in
    ``apps``; ``list_apps`` returns the list of valid app names.

    Args:
        apps: List of ``UseCaseAppConfig``.
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
        and an ``sdl`` string showing the method signature plus full type
        definitions for the return DTO and every nested DTO reachable
        through its fields. Use the ``sdl`` field to learn nested DTO
        shapes (e.g. what fields ``owner_detail: UserSummary`` exposes)
        without trial-and-error in ``compose_query``.

        Use this after ``describe_compose_schema`` to learn a specific
        method's signature before calling it via ``compose_query``.

        Args:
            app_name: Name of the application (from ``list_apps``).
            service_name: Name of the service (from ``describe_compose_schema``).
            method_name: Name of the method (from ``describe_compose_schema``).

        Returns:
            Dictionary with ``success``, ``data`` (``{name, kind,
            description, args, returns, sdl?}``), and a ``hint`` pointing
            to ``compose_query``. On failure: ``success=False``,
            ``error``, ``error_type``.
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

        method_info: dict[str, Any] = {
            "name": method_name,
            "kind": kind,
            "description": (
                meta.get("description") if isinstance(meta, dict) else None
            ),
            "args": _build_args_info(func),
            "returns": _python_type_to_str(return_anno),
        }

        # Focused SDL: method signature + return type + every reachable
        # nested DTO. None when the method returns a scalar (no nested
        # types to describe) or when schema-building fails — both are
        # safe to skip.
        try:
            sdl = _method_sdl(app, service_name, method_name)
            if sdl is not None:
                method_info["sdl"] = sdl
        except Exception:
            pass

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


async def _extract_context(
    app: "UseCaseResources", ctx: "Context"
) -> dict | None:
    """Call the app's ``context_extractor`` if configured.

    Returns ``None`` when no extractor is set or no context is available
    (e.g. MCP request context missing). Awaitable results are awaited.
    """
    if app.context_extractor is None or ctx is None:
        return None
    result = app.context_extractor(ctx)
    if inspect.isawaitable(result):
        return await result
    return result


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


def _method_sdl(app: Any, service_name: str, method_name: str) -> str | None:
    """Focused SDL for one method: signature + return type's transitive closure.

    Returns a GraphQL SDL string showing:
    - The method signature (args + return type) as a comment header
    - Full type definitions for the return DTO and every nested DTO
      reachable through its fields (handles cycles)

    Returns ``None`` if the method or its return type can't be located
    in the built schema (e.g. scalar returns have no nested types to
    print).
    """
    from graphql.utilities import print_type

    from pydantic_resolve.use_case.compose_schema import build_compose_schema

    schema = build_compose_schema(app)

    service_field = schema.query_type.fields.get(service_name)
    if service_field is None:
        return None
    service_type = _unwrap_type(service_field.type)
    method_field = service_type.fields.get(method_name) if service_type else None
    if method_field is None:
        return None

    # Collect reachable object types from the return type
    reachable: dict[str, Any] = {}
    _collect_reachable_types(method_field.type, schema.type_map, reachable)

    sdl_parts: list[str] = []
    # Method signature as a comment header
    args_sdl = ", ".join(
        f"{name}: {_graphql_type_to_sdl(arg.type)}"
        for name, arg in method_field.args.items()
    )
    sdl_parts.append(
        f"# {service_name}.{method_name}({args_sdl}): "
        f"{_graphql_type_to_sdl(method_field.type)}"
    )
    for type_name, type_def in sorted(reachable.items()):
        sdl_parts.append(print_type(type_def))
    return "\n\n".join(sdl_parts)


def _unwrap_type(type_ref: Any) -> Any:
    """Peel NonNull / List wrappers to get the underlying named type."""
    while hasattr(type_ref, "of_type"):
        type_ref = type_ref.of_type
    return type_ref


def _graphql_type_to_sdl(type_ref: Any) -> str:
    """Render a graphql-core type reference as SDL syntax.

    ``GraphQLNonNull(GraphQLList(GraphQLNonNull(GraphQLObjectType(X))))``
    → ``[X!]!``
    """
    type_name = getattr(type_ref, "name", None)
    if type_name is not None:
        return type_name
    inner = getattr(type_ref, "of_type", None)
    if inner is None:
        return str(type_ref)
    inner_sdl = _graphql_type_to_sdl(inner)
    # GraphQLNonNull wraps as ``T!``; GraphQLList wraps as ``[T]``
    class_name = type(type_ref).__name__
    if class_name == "GraphQLNonNull":
        return f"{inner_sdl}!"
    if class_name == "GraphQLList":
        return f"[{inner_sdl}]"
    return inner_sdl


def _collect_reachable_types(
    type_ref: Any, type_map: dict[str, Any], seen: dict[str, Any]
) -> None:
    """DFS-walk a graphql-core type reference, recording every object type.

    Used to build the transitive closure of types reachable from a
    method's return type — so the SDL response shows nested DTOs
    without dumping the entire schema.
    """
    from graphql.type import GraphQLObjectType

    core = _unwrap_type(type_ref)
    name = getattr(core, "name", None)
    if name is None or name in seen:
        return
    if isinstance(core, GraphQLObjectType):
        seen[name] = core
        for field in core.fields.values():
            _collect_reachable_types(field.type, type_map, seen)



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
