"""Build a graphql-core ``GraphQLSchema`` describing a UseCase app's compose surface.

The schema mirrors the fixed 3-level compose query hierarchy:

    type Query {
      SprintService: SprintServiceQuery!
      TaskService: TaskServiceQuery!
    }

    type SprintServiceQuery {
      list_sprints: [SprintDTO!]!
      get_sprint(sprint_id: Int!): SprintDTO
    }

Each registered ``UseCaseService`` becomes an ``ObjectType`` whose fields
are its ``@query`` / ``@mutation`` methods. Method arguments become
``GraphQLArgument`` s; the return annotation becomes the field type via
``pydantic_to_graphql_type``.

The resulting ``GraphQLSchema`` is what graphql-core's native
introspection expects, so GraphiQL works out of the box when this is
served through any HTTP endpoint that routes ``__schema`` / ``__type``
queries to ``compose_introspect``.
"""

from __future__ import annotations

import inspect
from typing import Annotated, Any, Callable, get_args, get_origin

from graphql import (
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLField,
    GraphQLFloat,
    GraphQLInt,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)

from pydantic_resolve.graphql.type_converter import pydantic_to_graphql_type
from pydantic_resolve.use_case.business import USE_CASE_METHODS_ATTR
from pydantic_resolve.use_case.context import FromContext
from pydantic_resolve.utils.types import _resolve_function_type_hints, get_return_annotation


def build_compose_schema(app: Any) -> GraphQLSchema:
    """Build a graphql-core schema describing ``compose_query``'s surface.

    Args:
        app: ``UseCaseResources`` from ``UseCaseManager.get_app``.

    Returns:
        A ``GraphQLSchema`` whose root Query type has one field per
        registered service. Each service is its own ``ObjectType``.
        Mutations appear as fields on the service type (not on a
        separate Mutation root) when ``app.enable_mutation`` is True.
    """
    type_cache: dict[Any, Any] = {}

    query_fields: dict[str, GraphQLField] = {}
    for service_name, service_cls in app.services.items():
        service_type = _build_service_object_type(
            service_name=service_name,
            service_cls=service_cls,
            enable_mutation=app.enable_mutation,
            type_cache=type_cache,
        )
        query_fields[service_name] = GraphQLField(
            type_=GraphQLNonNull(service_type),
            description=(service_cls.__doc__ or None),
        )

    if not query_fields:
        # graphql-core refuses to build a schema with an empty Query type;
        # provide a placeholder so introspection at least returns something.
        query_fields["_empty"] = GraphQLField(
            type_=GraphQLString,
            description="No services registered.",
        )

    root_query = GraphQLObjectType(
        name="Query",
        fields=query_fields,
        description="Root of the compose_query schema.",
    )

    return GraphQLSchema(query=root_query, mutation=None)


# ============================================================================
# Internals
# ============================================================================


def _build_service_object_type(
    service_name: str,
    service_cls: type,
    enable_mutation: bool,
    type_cache: dict[Any, Any],
) -> GraphQLObjectType:
    """Build the ObjectType representing a single service.

    Each ``@query`` / ``@mutation`` method on the service becomes a
    GraphQLField; ``cls`` and ``FromContext`` params are skipped.
    """
    methods: dict[str, dict[str, Any]] = getattr(
        service_cls, USE_CASE_METHODS_ATTR, {}
    )

    fields: dict[str, GraphQLField] = {}
    for method_name, meta in methods.items():
        kind = meta.get("kind", "query") if isinstance(meta, dict) else "query"
        if kind == "mutation" and not enable_mutation:
            continue

        method = meta["method"]
        func = getattr(method, "__func__", method)
        return_anno = get_return_annotation(method)
        field_type = (
            pydantic_to_graphql_type(return_anno, type_cache)
            if return_anno is not None
            else GraphQLString
        )
        args = _build_method_args(func, type_cache)

        fields[method_name] = GraphQLField(
            type_=field_type,
            args=args or None,
            description=_docstring_or_meta(meta),
        )

    if not fields:
        # graphql-core requires ObjectType to have at least one field
        fields["_no_methods"] = GraphQLField(
            type_=GraphQLString,
            description=f"Service '{service_name}' exposes no methods.",
        )

    return GraphQLObjectType(
        name=f"{service_name}Query",
        fields=fields,
        description=(service_cls.__doc__ or None),
    )


def _build_method_args(
    func: Callable,
    type_cache: dict[Any, Any],
) -> dict[str, GraphQLArgument]:
    """Build GraphQLArgument dict for a method's parameters.

    Skips ``cls`` and parameters annotated with ``FromContext``.
    Uses parameter defaults when present; otherwise the arg is required
    (wrapped in ``GraphQLNonNull`` via the type converter).
    """
    sig = inspect.signature(func)
    hints = _resolve_function_type_hints(func)

    args: dict[str, GraphQLArgument] = {}
    for name, param in sig.parameters.items():
        if name == "cls":
            continue
        anno = hints.get(name, param.annotation)
        if _is_from_context_param(anno):
            continue
        if anno is inspect.Parameter.empty or anno is None:
            anno = str  # unknown → default to String

        has_default = param.default is not inspect.Parameter.empty
        arg_type = pydantic_to_graphql_type(anno, type_cache)
        if has_default:
            # Strip NonNull so the arg becomes optional
            if isinstance(arg_type, GraphQLNonNull):
                arg_type = arg_type.of_type
            args[name] = GraphQLArgument(
                type_=arg_type,
                default_value=param.default,
                description=None,
            )
        else:
            args[name] = GraphQLArgument(type_=arg_type, description=None)
    return args


def _is_from_context_param(annotation: Any) -> bool:
    if annotation is None or annotation is inspect.Parameter.empty:
        return False
    if get_origin(annotation) is not Annotated:
        return False
    return any(isinstance(arg, FromContext) for arg in get_args(annotation))


def _docstring_or_meta(meta: dict[str, Any]) -> str | None:
    desc = meta.get("description") if isinstance(meta, dict) else None
    if desc:
        return desc
    return None


__all__ = ["build_compose_schema"]
