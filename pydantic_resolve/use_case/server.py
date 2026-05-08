"""UseCase MCP Server — four-layer progressive disclosure for use case methods.

Creates an independent FastMCP server that exposes UseCaseService methods
to AI agents via progressive disclosure:
- list_apps: discover available applications
- list_services: list services in an app
- describe_service: get method signatures for a service
- call_use_case: execute a specific method
"""

from __future__ import annotations

import inspect
import json
from typing import TYPE_CHECKING, Annotated, Any, get_args, get_origin, get_type_hints

from fastmcp.server.context import Context
from pydantic import BaseModel

from pydantic_resolve.graphql.mcp.types.errors import (
    MCPErrors,
    create_error_response,
    create_success_response,
)
from pydantic_resolve.use_case.business import USE_CASE_METHODS_ATTR
from pydantic_resolve.use_case.context import FromContext
from pydantic_resolve.use_case.manager import UseCaseManager
from pydantic_resolve.use_case.types import UseCaseAppConfig

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from pydantic_resolve.use_case.manager import UseCaseResources


def create_use_case_mcp_server(
    apps: list[UseCaseAppConfig],
    name: str = "Pydantic-Resolve UseCase API",
) -> "FastMCP":
    """Create an MCP server that exposes UseCase services as tools.

    Args:
        apps: List of UseCaseAppConfig instances, each containing a group
            of UseCaseService subclasses.
        name: Name of the MCP server (shown in MCP clients).

    Returns:
        A configured FastMCP server instance.

    Example::

        mcp = create_use_case_mcp_server(
            apps=[
                UseCaseAppConfig(
                    name="project",
                    services=[SprintService, TaskService],
                ),
            ],
            name="Project UseCase API",
        )
        mcp.run()
    """
    from fastmcp import FastMCP

    if not apps:
        raise ValueError("apps list cannot be empty")

    manager = UseCaseManager(apps)
    mcp = FastMCP(name)

    # Layer 0: Application discovery
    @mcp.tool()
    def list_apps() -> dict[str, Any]:
        """List all available UseCase applications.

        Returns a list of all configured applications with their metadata:
        - name: Application name
        - description: Application description
        - services_count: Number of services in the app

        IMPORTANT: All subsequent tool calls (except this one) require
        the app_name parameter. Choose an app_name from this list.

        Use this as the first step to discover what APIs are available,
        then use list_services to explore services within an app.

        Returns:
            Dictionary with success status, app list, and usage hints

        Example response:
            {
                "success": true,
                "data": [{"name": "project", "description": "...", "services_count": 2}],
                "hint": "Use list_services(app_name='project') ..."
            }
        """
        try:
            apps_info = []
            for app in manager.apps.values():
                apps_info.append({
                    "name": app.name,
                    "description": app.description,
                    "services_count": len(app.services),
                })

            app_names = [a["name"] for a in apps_info]
            hint = (
                f"IMPORTANT: All subsequent tool calls require app_name parameter. "
                f"Available apps: {app_names}. "
                f"Example: list_services(app_name='{app_names[0] if app_names else 'app_name'}')"
            )

            return {
                "success": True,
                "data": apps_info,
                "hint": hint,
            }
        except Exception as e:
            return create_error_response(str(e), MCPErrors.INTERNAL_ERROR)

    # Layer 1: Service listing
    @mcp.tool()
    def list_services(app_name: str) -> dict[str, Any]:
        """List all available UseCase services for an application.

        Returns a lightweight list of service names, descriptions, and
        method counts. Use this after list_apps to discover services,
        then use describe_service to explore a specific service's methods.

        Args:
            app_name: Name of the application (from list_apps).

        Returns:
            Dictionary with service list and usage hints.

        Example:
            list_services(app_name="project")
        """
        try:
            app = manager.get_app(app_name)
            services_info = app.introspector.list_services()

            service_names = [s["name"] for s in services_info]
            hint = (
                f"Working with app '{app_name}'. "
                f"Use describe_service(app_name='{app_name}', service_name='...') "
                f"to explore methods. Available services: {service_names}."
            )

            return {
                "success": True,
                "data": services_info,
                "hint": hint,
            }
        except ValueError as e:
            return create_error_response(str(e), MCPErrors.APP_NOT_FOUND)
        except Exception as e:
            return create_error_response(str(e), MCPErrors.INTERNAL_ERROR)

    # Layer 2: Method description
    @mcp.tool()
    def describe_service(app_name: str, service_name: str) -> dict[str, Any]:
        """Get detailed method info for a specific UseCase service.

        Returns all methods on the service with their names, descriptions,
        parameter schemas (JSON Schema), and return type schemas.
        Use this after list_services to understand what methods are available,
        then use call_use_case to execute a specific method.

        Args:
            app_name: Name of the application (from list_apps).
            service_name: Name of the service (from list_services).

        Returns:
            Dictionary with success, data (service details with methods and types), and hint.

        Example::

            describe_service(app_name="project", service_name="SprintService")
        """
        try:
            app = manager.get_app(app_name)
            info = app.introspector.describe_service(service_name)
            if info is None:
                return create_error_response(
                    f"Service '{service_name}' not found in app '{app_name}'. "
                    f"Use list_services(app_name='{app_name}') to see available services.",
                    MCPErrors.TYPE_NOT_FOUND,
                )

            method_names = [m["name"] for m in info.get("methods", [])]
            hint = (
                f"Methods in '{service_name}' (app: '{app_name}'): {method_names}. "
                f"Use call_use_case(app_name='{app_name}', "
                f"service_name='{service_name}', "
                f"method_name='...', params='{{...}}') to execute."
            )

            result = create_success_response(info)
            result["hint"] = hint
            return result
        except ValueError as e:
            return create_error_response(str(e), MCPErrors.APP_NOT_FOUND)
        except Exception as e:
            return create_error_response(str(e), MCPErrors.INTERNAL_ERROR)

    # Layer 3: Execute use case
    @mcp.tool()
    async def call_use_case(
        app_name: str,
        service_name: str,
        method_name: str,
        params: str = "{}",
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict[str, Any]:
        """Execute a use case method on a specific service.

        Call a method discovered via describe_service. The params argument
        should be a JSON object string matching the method's parameter schema.

        Args:
            app_name: Name of the application.
            service_name: Name of the service.
            method_name: Name of the method to call.
            params: JSON string with method parameters (default: "{}").

        Returns:
            Dictionary with success, data (method result), and hint.

        Examples::

            # No parameters
            call_use_case(app_name="project", service_name="SprintService",
                     method_name="list_sprints")

            # With parameters
            call_use_case(
                app_name="project",
                service_name="SprintService",
                method_name="get_sprint",
                params='{"sprint_id": 1}'
            )
        """
        # Parse params JSON
        try:
            kwargs = json.loads(params) if params else {}
        except json.JSONDecodeError as e:
            return create_error_response(
                f"Invalid JSON in params: {e}",
                MCPErrors.VALIDATION_ERROR,
            )

        if not isinstance(kwargs, dict):
            return create_error_response(
                "params must be a JSON object (dict), not an array or scalar",
                MCPErrors.VALIDATION_ERROR,
            )

        # Look up app
        try:
            app = manager.get_app(app_name)
        except ValueError:
            return create_error_response(
                f"App '{app_name}' not found. "
                f"Use list_apps() to see available apps.",
                MCPErrors.APP_NOT_FOUND,
            )

        # Look up service
        service_cls = app.services.get(service_name)
        if service_cls is None:
            available = list(app.services.keys())
            return create_error_response(
                f"Service '{service_name}' not found in app '{app_name}'. "
                f"Available services: {available}",
                MCPErrors.TYPE_NOT_FOUND,
            )

        # Look up method
        methods = getattr(service_cls, USE_CASE_METHODS_ATTR)
        if method_name not in methods:
            available = list(methods.keys())
            return create_error_response(
                f"Method '{method_name}' not found in service '{service_name}'. "
                f"Available methods: {available}",
                MCPErrors.OPERATION_NOT_FOUND,
            )

        # Execute
        try:
            method = getattr(service_cls, method_name)

            # Extract context and merge FromContext params into kwargs
            context = await _extract_context(app, ctx)
            from_context_params = _get_from_context_params(method)
            if from_context_params:
                if context is None:
                    context = {}
                sig = inspect.signature(method)
                for param_name in from_context_params:
                    if param_name in context:
                        kwargs[param_name] = context[param_name]
                    elif param_name not in kwargs and sig.parameters[param_name].default is inspect.Parameter.empty:
                        return create_error_response(
                            f"Required FromContext parameter '{param_name}' "
                            f"not found in context for {service_name}.{method_name}",
                            MCPErrors.VALIDATION_ERROR,
                        )

            result = await method(**kwargs)
        except TypeError as e:
            return create_error_response(
                f"Parameter error calling {service_name}.{method_name}: {e}",
                MCPErrors.VALIDATION_ERROR,
            )
        except Exception as e:
            return create_error_response(
                f"Error executing {service_name}.{method_name}: {e}",
                MCPErrors.QUERY_EXECUTION_ERROR,
            )

        # Serialize result
        data = _serialize_result(result)

        response = create_success_response(data)
        response["hint"] = (
            f"Executed {app_name}.{service_name}.{method_name}. "
            f"Use describe_service(app_name='{app_name}', service_name='{service_name}') "
            f"to explore more methods."
        )
        return response

    async def _extract_context(
        app: "UseCaseResources", ctx: "Context"
    ) -> dict | None:
        """Call the app's context_extractor if configured, returning a context dict."""
        if app.context_extractor is None or ctx is None:
            return None
        result = app.context_extractor(ctx)
        if inspect.isawaitable(result):
            return await result
        return result

    def _get_from_context_params(method: callable) -> set[str]:
        """Return parameter names annotated with FromContext."""
        from_context_params = set()
        try:
            hints = get_type_hints(method, include_extras=True)
        except Exception:
            hints = {}
        sig = inspect.signature(method)
        for name in sig.parameters:
            annotation = hints.get(name)
            if annotation is not None and get_origin(annotation) is Annotated:
                for arg in get_args(annotation):
                    if isinstance(arg, FromContext):
                        from_context_params.add(name)
                        break
        return from_context_params

    return mcp


def _serialize_result(result: Any) -> Any:
    """Serialize a method result to a JSON-friendly structure."""
    if result is None:
        return None

    if isinstance(result, BaseModel):
        return result.model_dump()

    if isinstance(result, list):
        return [_serialize_result(item) for item in result]

    if isinstance(result, dict):
        return result

    if isinstance(result, (str, int, float, bool)):
        return result

    # Fallback: try model_dump for any Pydantic-like object
    if hasattr(result, "model_dump"):
        return result.model_dump()

    return result
