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
from typing import Any, Callable

from graphql import (
    GraphQLArgument,
    GraphQLField,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)

from pydantic_resolve.graphql.type_converter import pydantic_to_graphql_type
from pydantic_resolve.use_case.business import iter_use_case_methods
from pydantic_resolve.use_case.context import is_from_context_annotation
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
    fields: dict[str, GraphQLField] = {}
    for method_name, _kind, meta in iter_use_case_methods(
        service_cls, enable_mutation=enable_mutation
    ):
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
        if is_from_context_annotation(anno):
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


def _docstring_or_meta(meta: dict[str, Any]) -> str | None:
    desc = meta.get("description") if isinstance(meta, dict) else None
    if desc:
        return desc
    return None


# ============================================================================
# SDL rendering (focused per-method view, used by describe_compose_method)
# ============================================================================


def method_sdl(schema: Any, service_name: str, method_name: str) -> str | None:
    """Focused SDL for one method: signature + return type's transitive closure.

    Returns a GraphQL SDL string showing:
    - The method signature (args + return type) as a comment header
    - Full type definitions for the return DTO and every nested DTO
      reachable through its fields (handles cycles)

    Returns ``None`` if the method or its return type can't be located
    in ``schema`` (e.g. scalar returns have no nested types to print).

    Callers should pass the cached ``app.compose_schema`` rather than
    rebuilding on each call.
    """
    from graphql.utilities import print_type

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


__all__ = ["build_compose_schema"]
