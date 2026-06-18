"""Selection projection for UseCase MCP responses.

This module implements a lightweight, DTO-only projection layer for
``call_use_case(selection=...)``.  It intentionally reuses the GraphQL
``QueryParser``/``FieldSelection`` structures while avoiding ERD-specific
response building behavior such as relationships, pagination, and FK fields.
"""

from __future__ import annotations

import inspect
import typing
from types import UnionType as _UnionType
from typing import Any, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, create_model
from pydantic_core import PydanticUndefined

from pydantic_resolve.graphql.exceptions import QueryParseError
from pydantic_resolve.graphql.query_parser import QueryParser
from pydantic_resolve.graphql.types import FieldSelection
from pydantic_resolve.utils.class_util import safe_issubclass
from pydantic_resolve.utils.types import get_core_types


_UNION_ORIGINS = (typing.Union, _UnionType)
_RESULT_FIELD = "__result"


class SelectionError(ValueError):
    """Raised when a UseCase MCP selection is invalid."""


def apply_selection(result: Any, return_annotation: Any, selection: str) -> Any:
    """Project a UseCase result into a dynamic Pydantic subset model.

    The returned value remains a Pydantic model/list of Pydantic models/None;
    final serialization is still handled by the existing MCP response layer.
    """
    field_selection = parse_selection(selection)
    root_model, root_annotation = _extract_root_model(return_annotation, result)
    subset_model = build_subset_model(root_model, field_selection)

    if result is None:
        return None

    try:
        selected_annotation = _replace_model_type(root_annotation, subset_model)
        return TypeAdapter(selected_annotation).validate_python(result)
    except Exception as e:  # pragma: no cover - exact pydantic errors vary
        raise SelectionError(f"Failed to apply selection: {e}") from e


def parse_selection(selection: str) -> FieldSelection:
    """Parse a rootless GraphQL-like selection into a FieldSelection tree."""
    if not selection or not selection.strip():
        raise SelectionError("selection cannot be empty")

    query = f"{{ {_RESULT_FIELD} {selection} }}"
    try:
        parsed = QueryParser().parse(query)
    except QueryParseError as e:
        raise SelectionError(str(e)) from e

    root = parsed.field_tree.get(_RESULT_FIELD)
    if root is None:
        raise SelectionError("selection could not be parsed")
    if root.arguments:
        raise SelectionError("selection arguments are not supported")
    if not root.sub_fields:
        raise SelectionError("selection must include at least one field")

    _reject_arguments(root)
    return root


def build_subset_model(
    model_type: type[BaseModel],
    field_selection: FieldSelection,
    path: str = "",
) -> type[BaseModel]:
    """Recursively build a dynamic Pydantic model for selected DTO fields."""
    if not field_selection.sub_fields:
        raise SelectionError(f"Selection for '{model_type.__name__}' cannot be empty")

    field_definitions: dict[str, tuple[Any, Any]] = {}
    for field_name, selection in field_selection.sub_fields.items():
        field_path = f"{path}.{field_name}" if path else field_name
        if field_name not in model_type.model_fields:
            available = list(model_type.model_fields.keys())
            raise SelectionError(
                f"Unknown field '{field_path}' on return type "
                f"'{model_type.__name__}'. Available fields: {available}"
            )

        field_info = model_type.model_fields[field_name]
        field_type = field_info.annotation
        nested_model_type = _get_pydantic_core_type(field_type)

        if nested_model_type is not None:
            if not selection.sub_fields:
                raise SelectionError(
                    f"Field '{field_path}' is a Pydantic object and requires sub-selection"
                )
            nested_subset = build_subset_model(nested_model_type, selection, field_path)
            selected_type = _replace_model_type(field_type, nested_subset)
        else:
            if selection.sub_fields:
                raise SelectionError(
                    f"Field '{field_path}' is not a Pydantic object and cannot have sub-selection"
                )
            selected_type = field_type

        field_definitions[field_name] = (selected_type, _field_default(field_info))

    return create_model(
        f"{model_type.__name__}Selection_{abs(hash(field_selection))}",
        __config__=ConfigDict(from_attributes=True, arbitrary_types_allowed=True),
        **field_definitions,
    )


def _reject_arguments(selection: FieldSelection, path: str = "") -> None:
    if selection.arguments:
        location = path or _RESULT_FIELD
        raise SelectionError(f"selection arguments are not supported at '{location}'")
    if not selection.sub_fields:
        return
    for field_name, sub_selection in selection.sub_fields.items():
        child_path = f"{path}.{field_name}" if path else field_name
        _reject_arguments(sub_selection, child_path)


def _extract_root_model(
    return_annotation: Any,
    result: Any,
) -> tuple[type[BaseModel], Any]:
    core_type = _get_pydantic_core_type(return_annotation)
    if core_type is not None:
        return core_type, return_annotation

    runtime_annotation = _infer_runtime_annotation(result)
    runtime_core_type = _get_pydantic_core_type(runtime_annotation)
    if runtime_core_type is not None:
        return runtime_core_type, runtime_annotation

    raise SelectionError(
        "selection is only supported for Pydantic return types "
        "(BaseModel, list[BaseModel], or optional variants)"
    )


def _infer_runtime_annotation(result: Any) -> Any:
    if isinstance(result, BaseModel):
        return result.__class__

    if not isinstance(result, list):
        return None

    item_type = None
    saw_none = False
    for item in result:
        if item is None:
            saw_none = True
            continue

        if not isinstance(item, BaseModel):
            return None

        current_type = item.__class__
        if item_type is None:
            item_type = current_type
        elif current_type is not item_type:
            return None

    if item_type is None:
        return None

    if saw_none:
        return list[item_type | None]

    return list[item_type]


def _get_pydantic_core_type(annotation: Any) -> type[BaseModel] | None:
    if annotation is None or annotation is inspect.Parameter.empty:
        return None
    core_types = get_core_types(annotation)
    pydantic_types = [tp for tp in core_types if safe_issubclass(tp, BaseModel)]
    if len(pydantic_types) == 1:
        return pydantic_types[0]
    return None


def _replace_model_type(annotation: Any, nested_model: type[BaseModel]) -> Any:
    annotation = _strip_annotated(annotation)

    if annotation is None or annotation is inspect.Parameter.empty:
        return nested_model

    if _is_list_annotation(annotation):
        args = get_args(annotation)
        inner = args[0] if args else Any
        return list[_replace_model_type(inner, nested_model)]

    if get_origin(annotation) in _UNION_ORIGINS:
        replaced_args = [_replace_model_type(arg, nested_model) for arg in get_args(annotation)]
        return _build_union_type(replaced_args)

    if _get_pydantic_core_type(annotation) is not None:
        return nested_model

    return annotation


def _build_union_type(args: list[Any]) -> Any:
    if not args:
        return Any

    union_type = args[0]
    for arg in args[1:]:
        union_type = union_type | arg
    return union_type


def _field_default(field_info: Any) -> Any:
    description = getattr(field_info, "description", None)
    default_factory = getattr(field_info, "default_factory", None)
    if default_factory is not None:
        return Field(default_factory=default_factory, description=description)

    default = getattr(field_info, "default", PydanticUndefined)
    if default is not PydanticUndefined:
        return Field(default=default, description=description)

    return Field(default=..., description=description)


def _strip_annotated(annotation: Any) -> Any:
    while get_origin(annotation) is typing.Annotated:
        args = get_args(annotation)
        if not args:
            break
        annotation = args[0]
    return annotation


def _is_optional_annotation(annotation: Any) -> bool:
    origin = get_origin(annotation)
    return origin in _UNION_ORIGINS and any(arg is type(None) for arg in get_args(annotation))


def _strip_optional(annotation: Any) -> Any:
    if not _is_optional_annotation(annotation):
        return annotation
    non_none = [arg for arg in get_args(annotation) if arg is not type(None)]
    if len(non_none) != 1:
        return annotation
    return non_none[0]


def _is_list_annotation(annotation: Any) -> bool:
    return get_origin(annotation) is list
