"""UseCase compose — GraphQL-style multi-method composition entry point.

Accepts a single GraphQL query with a fixed 3-level hierarchy::

    {
      ServiceA {
        methodX(arg: 1) { fieldA fieldB }
        methodY { fieldC }
      }
      ServiceB {
        methodZ { fieldD }
      }
    }

Each (service, method) pair is invoked concurrently. Results are wrapped
into a dynamic Pydantic model and passed through the existing ``Resolver``
so any ``resolve_*`` / ``AutoLoad`` on the DTOs still fires. Per-method
field selection (the third level) is then projected via
``build_subset_model`` before serialization.

This module is intentionally self-contained: it reuses public utilities
(``QueryParser``, ``build_subset_model``, ``Resolver``) but does not
modify ``server.py`` internals. The MCP tool ``compose_query`` in
``server.py`` is a thin wrapper around :func:`compose_and_resolve`.
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Annotated, Any, get_args, get_origin

from pydantic import BaseModel, ConfigDict, TypeAdapter, create_model
from pydantic_core import PydanticUndefined

from pydantic_resolve.graphql.exceptions import QueryParseError
from pydantic_resolve.graphql.query_parser import QueryParser
from pydantic_resolve.graphql.types import FieldSelection, ParsedQuery
from pydantic_resolve.resolver import Resolver
from pydantic_resolve.use_case.business import USE_CASE_METHODS_ATTR
from pydantic_resolve.use_case.context import FromContext
from pydantic_resolve.use_case.selection import (
    SelectionError,
    _get_pydantic_core_type,
    _replace_model_type,
    build_subset_model,
)
from pydantic_resolve.utils.types import _resolve_function_type_hints, get_return_annotation


class ComposeError(ValueError):
    """Raised for any compose-time validation or execution failure.

    ``error_type`` matches a :class:`MCPErrors` enum **value** (lowercase
    string, e.g. ``"validation_error"``, ``"type_not_found"``) so the MCP
    tool layer can pick the right code without re-parsing the message.
    """

    def __init__(self, message: str, error_type: str = "validation_error"):
        super().__init__(message)
        self.error_type = error_type


@dataclass
class ServiceExecutionPlan:
    service_name: str
    method_name: str
    service_cls: type
    method: Any
    func: Any
    method_meta: dict
    method_selection: FieldSelection
    return_anno: Any


async def compose_and_resolve(
    app: Any,
    query: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Parse, validate, execute, resolve, and project a compose query.

    Args:
        app: :class:`UseCaseResources` instance (from ``UseCaseManager.get_app``).
        query: GraphQL query string. Fixed 3-level hierarchy:
            root → service → method → DTO field selection.
        context: Request-scoped context dict. Flows into ``Resolver``
            and into method params annotated with ``FromContext``.

    Returns:
        Nested dict shaped like ``{service: {method: result}}``.

    Raises:
        ComposeError: For any validation or execution failure. The
            ``error_type`` attribute carries the MCP error code.
    """
    parsed = _parse_query(query)
    if not parsed.field_tree:
        raise ComposeError("Query is empty", "validation_error")

    plans = _build_plans(app, parsed)

    results = await asyncio.gather(*[_exec_method(app, p, context) for p in plans])
    plan_to_result: dict[int, Any] = {id(p): r for p, r in zip(plans, results)}

    root_instance = _build_wrapper_instance(plans, plan_to_result)

    if _has_pydantic_return(plans):
        try:
            resolved = await Resolver(context=context).resolve(root_instance)
        except ComposeError:
            raise
        except Exception as e:
            raise ComposeError(f"Resolver error: {e}", "internal_error") from e
    else:
        resolved = root_instance

    output: dict[str, Any] = {}
    for plan in plans:
        svc_dict = output.setdefault(plan.service_name, {})
        svc_instance = getattr(resolved, plan.service_name)
        method_value = getattr(svc_instance, plan.method_name)
        svc_dict[plan.method_name] = _project_one(method_value, plan)
    return output


# ============================================================================
# Parsing & validation
# ============================================================================


def _parse_query(query: str) -> ParsedQuery:
    if not query or not query.strip():
        raise ComposeError("Query is empty", "validation_error")
    try:
        return QueryParser().parse(query)
    except QueryParseError as e:
        raise ComposeError(str(e), "validation_error") from e


def _build_plans(app: Any, parsed: ParsedQuery) -> list[ServiceExecutionPlan]:
    plans: list[ServiceExecutionPlan] = []
    for service_name, service_selection in parsed.field_tree.items():
        service_cls = _resolve_service(app, service_name)
        _reject_arguments(service_selection, f"Service '{service_name}'")

        if not service_selection.sub_fields:
            raise ComposeError(
                f"Service '{service_name}' has no methods selected",
                "validation_error",
            )

        for method_name, method_selection in service_selection.sub_fields.items():
            method_meta = _resolve_method(service_cls, method_name, service_name)
            _check_mutation_permission(app, method_meta, service_name, method_name)

            method = getattr(service_cls, method_name)
            func = getattr(method, "__func__", method)
            return_anno = get_return_annotation(method)

            plans.append(ServiceExecutionPlan(
                service_name=service_name,
                method_name=method_name,
                service_cls=service_cls,
                method=method,
                func=func,
                method_meta=method_meta,
                method_selection=method_selection,
                return_anno=return_anno,
            ))
    return plans


def _resolve_service(app: Any, service_name: str) -> type:
    services = app.services
    if service_name not in services:
        available = list(services.keys())
        raise ComposeError(
            f"Service '{service_name}' not found in app '{app.name}'. "
            f"Available services: {available}",
            "type_not_found",
        )
    return services[service_name]


def _resolve_method(service_cls: type, method_name: str, service_name: str) -> dict:
    methods = getattr(service_cls, USE_CASE_METHODS_ATTR, {})
    if method_name not in methods:
        available = list(methods.keys())
        raise ComposeError(
            f"Method '{method_name}' not found in service '{service_name}'. "
            f"Available methods: {available}",
            "operation_not_found",
        )
    return methods[method_name]


def _check_mutation_permission(
    app: Any, method_meta: dict, service_name: str, method_name: str
) -> None:
    if not app.enable_mutation and method_meta.get("kind") == "mutation":
        raise ComposeError(
            f"Method '{method_name}' is a mutation and mutations are disabled "
            f"for app '{app.name}'.",
            "operation_not_found",
        )


def _reject_arguments(selection: FieldSelection, location: str) -> None:
    if selection.arguments:
        raise ComposeError(
            f"Arguments are not allowed on {location}.",
            "validation_error",
        )


# ============================================================================
# Execution
# ============================================================================


async def _exec_method(
    app: Any, plan: ServiceExecutionPlan, context: dict[str, Any] | None
) -> Any:
    kwargs = _prepare_method_kwargs(plan, context)
    try:
        return await plan.method(**kwargs)
    except ComposeError:
        raise
    except Exception as e:
        kind = plan.method_meta.get("kind", "query")
        err_type = (
            "mutation_execution_error" if kind == "mutation"
            else "query_execution_error"
        )
        raise ComposeError(
            f"Error executing {plan.service_name}.{plan.method_name}: {e}",
            err_type,
        ) from e


def _prepare_method_kwargs(
    plan: ServiceExecutionPlan, context: dict[str, Any] | None
) -> dict[str, Any]:
    func = plan.func
    raw_args = dict(plan.method_selection.arguments or {})
    from_context_params = _get_from_context_params(func)

    sig = inspect.signature(func)
    hints = _resolve_function_type_hints(func)
    valid_params = {n for n in sig.parameters if n != "cls"}

    for arg_name in raw_args:
        if arg_name not in valid_params:
            raise ComposeError(
                f"Unexpected argument '{arg_name}' for method "
                f"'{plan.service_name}.{plan.method_name}'. "
                f"Valid arguments: {sorted(valid_params)}",
                "validation_error",
            )

    kwargs: dict[str, Any] = {}
    for name, param in sig.parameters.items():
        if name == "cls":
            continue
        anno = hints.get(name, param.annotation)

        if name in raw_args:
            kwargs[name] = _coerce_strict(raw_args[name], anno, name, plan)
        elif name in from_context_params:
            if context is not None and name in context:
                kwargs[name] = context[name]
            elif param.default is inspect.Parameter.empty:
                raise ComposeError(
                    f"Required FromContext parameter '{name}' not found in context "
                    f"for {plan.service_name}.{plan.method_name}",
                    "validation_error",
                )
        elif param.default is inspect.Parameter.empty:
            raise ComposeError(
                f"Missing required argument '{name}' for method "
                f"'{plan.service_name}.{plan.method_name}'.",
                "validation_error",
            )
    return kwargs


def _coerce_strict(
    value: Any, annotation: Any, arg_name: str, plan: ServiceExecutionPlan
) -> Any:
    if value is None:
        return None
    if annotation is inspect.Parameter.empty or annotation is None:
        return value
    try:
        return TypeAdapter(annotation).validate_python(value)
    except Exception as e:
        raise ComposeError(
            f"Failed to coerce argument '{arg_name}' for method "
            f"'{plan.service_name}.{plan.method_name}': {e}",
            "validation_error",
        ) from e


def _get_from_context_params(method: Any) -> set[str]:
    from_context_params: set[str] = set()
    hints = _resolve_function_type_hints(method)
    sig = inspect.signature(method)
    for name in sig.parameters:
        if name == "cls":
            continue
        annotation = hints.get(name)
        if annotation is not None and get_origin(annotation) is Annotated:
            for arg in get_args(annotation):
                if isinstance(arg, FromContext):
                    from_context_params.add(name)
                    break
    return from_context_params


# ============================================================================
# Wrapper model + Resolver
# ============================================================================


def _has_pydantic_return(plans: list[ServiceExecutionPlan]) -> bool:
    for p in plans:
        if p.return_anno is not None and _get_pydantic_core_type(p.return_anno) is not None:
            return True
    return False


def _build_wrapper_instance(
    plans: list[ServiceExecutionPlan], plan_to_result: dict[int, Any]
) -> BaseModel:
    by_service: dict[str, list[ServiceExecutionPlan]] = {}
    for p in plans:
        by_service.setdefault(p.service_name, []).append(p)

    service_field_defs: dict[str, tuple[Any, Any]] = {}
    service_model_classes: dict[str, type[BaseModel]] = {}

    for svc_name, svc_plans in by_service.items():
        method_fields: dict[str, tuple[Any, Any]] = {}
        for p in svc_plans:
            anno = p.return_anno if p.return_anno is not None else Any
            method_fields[p.method_name] = (anno, ...)
        svc_model = create_model(
            f"{svc_name}Compose",
            __config__=ConfigDict(arbitrary_types_allowed=True),
            **method_fields,
        )
        service_model_classes[svc_name] = svc_model
        service_field_defs[svc_name] = (svc_model, ...)

    root_model = create_model(
        "ComposeRoot",
        __config__=ConfigDict(arbitrary_types_allowed=True),
        **service_field_defs,
    )

    svc_instances: dict[str, BaseModel] = {}
    for svc_name, svc_plans in by_service.items():
        method_values = {p.method_name: plan_to_result[id(p)] for p in svc_plans}
        svc_instances[svc_name] = service_model_classes[svc_name](**method_values)

    return root_model(**svc_instances)


# ============================================================================
# Selection projection (post-Resolver)
# ============================================================================


def _project_one(result: Any, plan: ServiceExecutionPlan) -> Any:
    if result is None:
        return None

    # Method-level arguments (e.g. get_sprint(sprint_id: 1)) are legitimate.
    # Only reject arguments on DTO leaf selections (sub_fields of the method).
    if plan.method_selection.sub_fields:
        for name, sub in plan.method_selection.sub_fields.items():
            _reject_arguments_recursive(sub, plan, f"{plan.method_name}.{name}")

    core_type = (
        _get_pydantic_core_type(plan.return_anno)
        if plan.return_anno is not None
        else None
    )

    if core_type is not None:
        if not plan.method_selection.sub_fields:
            raise ComposeError(
                f"Method '{plan.service_name}.{plan.method_name}' returns an object "
                f"type and requires field selection (e.g. '{{ id name }}').",
                "validation_error",
            )
        try:
            subset_model = build_subset_model(core_type, plan.method_selection)
            projected_anno = _replace_model_type(plan.return_anno, subset_model)
            projected = TypeAdapter(projected_anno).validate_python(result)
        except SelectionError as e:
            raise ComposeError(str(e), "validation_error") from e
        return _serialize_result(projected)

    return _serialize_result(result)


def _reject_arguments_recursive(
    selection: FieldSelection, plan: ServiceExecutionPlan, path: str
) -> None:
    if selection.arguments:
        raise ComposeError(
            f"Arguments are not allowed on DTO field '{path}' for "
            f"{plan.service_name}.{plan.method_name}.",
            "validation_error",
        )
    if not selection.sub_fields:
        return
    for name, sub in selection.sub_fields.items():
        child_path = f"{path}.{name}" if path else name
        _reject_arguments_recursive(sub, plan, child_path)


def _serialize_result(result: Any) -> Any:
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
    if hasattr(result, "model_dump"):
        return result.model_dump()
    return result
