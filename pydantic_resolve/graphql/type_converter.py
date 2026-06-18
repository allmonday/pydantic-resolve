"""Convert Python / Pydantic type annotations to graphql-core GraphQLType.

Used by ``compose_schema.build_compose_schema`` to assemble a real
``graphql.GraphQLSchema`` so that graphql-core's native introspection
(``introspection_from_schema`` / ``GraphQL.execute``) can serve
GraphiQL-compatible ``__schema`` / ``__type`` queries.

Nullability semantics follow GraphQL conventions:

============================  ==================
Python annotation             GraphQL
============================  ==================
``int``                       ``Int!``
``Optional[int]``             ``Int``
``list[int]``                 ``[Int!]!``
``list[Optional[int]]``       ``[Int]!``
``Optional[list[int]]``       ``[Int!]``
``Optional[list[Opt[int]]]``  ``[Int]``
============================  ==================

Recursion (Pydantic ``BaseModel`` self-reference, multi-service shared
DTOs) is handled via a shared ``type_cache`` populated lazily; the
GraphQLObjectType ``fields`` is supplied as a thunk so graphql-core
resolves types lazily after the cache is fully populated.
"""

from __future__ import annotations

import typing
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Union
from uuid import UUID

from pydantic import BaseModel
from graphql import (
    GraphQLBoolean,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLFloat,
    GraphQLID,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLString,
    GraphQLType,
)

from pydantic_resolve.utils.class_util import safe_issubclass
from pydantic_resolve.utils.types import _is_list, _is_optional

try:  # Python 3.10+ PEP 604 unions
    from types import UnionType as _UnionType
except ImportError:  # pragma: no cover
    _UnionType = ()


# Scalars without a native GraphQL equivalent fall back to GraphQLString.
# Users can override the schema post-build if they want custom scalars.
_SCALAR_MAP: dict[Any, Any] = {
    int: GraphQLInt,
    str: GraphQLString,
    bool: GraphQLBoolean,
    float: GraphQLFloat,
    bytes: GraphQLString,
    Decimal: GraphQLString,
    UUID: GraphQLID,
    datetime: GraphQLString,  # ISO 8601 string
    date: GraphQLString,
    time: GraphQLString,
}


def pydantic_to_graphql_type(
    annotation: Any,
    type_cache: dict[Any, Any],
) -> GraphQLType:
    """Convert a Python type annotation to a graphql-core ``GraphQLType``.

    Args:
        annotation: Python type annotation (Pydantic field type, method
            return type, or method arg type).
        type_cache: Shared cache dict for ``GraphQLObjectType`` /
            ``GraphQLEnumType``. Must be the same dict across a single
            schema build so cycles and shared types resolve correctly.

    Returns:
        A graphql-core type, wrapped in ``GraphQLNonNull`` unless the
        annotation is ``Optional[T]`` at this level.
    """
    if annotation is None or annotation is type(None):
        return GraphQLString

    # Annotated[X, ...] — strip metadata, keep underlying type
    annotation = _strip_annotated(annotation)

    is_optional = _is_optional(annotation)
    if is_optional:
        annotation = _peel_optional(annotation)

    result = _build_nullable_type(annotation, type_cache)

    if not is_optional:
        return GraphQLNonNull(result)
    return result


def _build_nullable_type(
    annotation: Any,
    type_cache: dict[Any, Any],
) -> GraphQLType:
    """Build the type WITHOUT wrapping in NonNull (caller decides)."""
    # list[T]
    if _is_list(annotation):
        args = typing.get_args(annotation)
        if not args:
            return GraphQLList(GraphQLNonNull(GraphQLString))
        inner = pydantic_to_graphql_type(args[0], type_cache)
        return GraphQLList(inner)

    # Union (non-Optional — Optional already peeled above). Take first member.
    origin = typing.get_origin(annotation)
    if origin in (Union, _UnionType) and type(origin) is not None:
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        if args:
            return _build_nullable_type(args[0], type_cache)
        return GraphQLString

    # Enum
    if _is_enum_class(annotation):
        return _get_or_create_enum_type(annotation, type_cache)

    # Pydantic BaseModel
    if safe_issubclass(annotation, BaseModel):
        return _get_or_create_object_type(annotation, type_cache)

    # Scalar
    if annotation in _SCALAR_MAP:
        return _SCALAR_MAP[annotation]

    # Unknown — fall back to String so schema is always buildable
    return GraphQLString


def _strip_annotated(annotation: Any) -> Any:
    while typing.get_origin(annotation) is Annotated:
        args = typing.get_args(annotation)
        if not args:
            break
        annotation = args[0]
    return annotation


def _peel_optional(annotation: Any) -> Any:
    """Return the non-None member of Optional[T] / Union[T, None]."""
    args = [a for a in typing.get_args(annotation) if a is not type(None)]
    if len(args) == 1:
        return args[0]
    if not args:
        return type(None)
    # Multi-member Union (rare, GraphQL has no union-of-arbitrary-types here)
    # Fold back into a Union without None so caller can take the first.
    return Union[tuple(args)]  # type: ignore[valid-type]


def _is_enum_class(annotation: Any) -> bool:
    try:
        return safe_issubclass(annotation, Enum)
    except TypeError:
        return False


def _get_or_create_object_type(
    model_cls: type[BaseModel],
    type_cache: dict[Any, Any],
) -> GraphQLObjectType:
    """Build (or fetch from cache) a GraphQLObjectType for a Pydantic model.

    Uses a ``fields`` thunk so that recursive / mutually-referential
    models resolve correctly: the cache entry is populated BEFORE the
    fields are scanned, so a self-reference returns the in-progress
    object.
    """
    cached = type_cache.get(model_cls)
    if cached is not None:
        return cached

    obj_type = GraphQLObjectType(
        name=model_cls.__name__,
        description=(model_cls.__doc__ or None),
        fields=lambda: _build_model_fields(model_cls, type_cache),
    )
    type_cache[model_cls] = obj_type
    return obj_type


def _build_model_fields(
    model_cls: type[BaseModel],
    type_cache: dict[Any, Any],
) -> dict[str, GraphQLField]:
    fields: dict[str, GraphQLField] = {}
    for name, field_info in model_cls.model_fields.items():
        anno = field_info.annotation
        try:
            fields[name] = GraphQLField(pydantic_to_graphql_type(anno, type_cache))
        except Exception:
            # Defensive: a single weird field shouldn't break the whole schema
            fields[name] = GraphQLField(GraphQLString)
    return fields


def _get_or_create_enum_type(
    enum_cls: type[Enum],
    type_cache: dict[Any, Any],
) -> GraphQLEnumType:
    cached = type_cache.get(enum_cls)
    if cached is not None:
        return cached

    values = {
        member.name: GraphQLEnumValue(value=member.value)
        for member in enum_cls
    }
    enum_type = GraphQLEnumType(
        name=enum_cls.__name__,
        values=values,
        description=(enum_cls.__doc__ or None),
    )
    type_cache[enum_cls] = enum_type
    return enum_type
