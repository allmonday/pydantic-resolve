from typing import Any, get_args
from pydantic import BaseModel
from pydantic_resolve.utils.class_util import safe_issubclass
from pydantic_resolve.utils.types import _is_optional, _is_list


def _collect_nested_types(model: type, collected: set[type] = None) -> set[type]:
    """Recursively collect all nested Pydantic BaseModel types from model_fields.

    Args:
        model: The Pydantic BaseModel class to scan
        collected: Set of already collected types (to avoid duplicates)

    Returns:
        Set of nested Pydantic BaseModel types
    """
    if collected is None:
        collected = set()

    for field_name, field_info in model.model_fields.items():
        field_type = field_info.annotation
        if field_type is None:
            continue

        # Handle List[SomeModel]
        if _is_list(field_type):
            args = get_args(field_type)
            if args:
                nested_type = args[0]
                if safe_issubclass(nested_type, BaseModel) and nested_type not in collected:
                    collected.add(nested_type)
                    _collect_nested_types(nested_type, collected)

        # Handle Union[SomeModel, None] or SomeModel | None
        elif _is_optional(field_type):
            args = get_args(field_type)
            for arg in args:
                if arg is not type(None) and safe_issubclass(arg, BaseModel) and arg not in collected:
                    collected.add(arg)
                    _collect_nested_types(arg, collected)

        # Handle SomeModel directly
        elif safe_issubclass(field_type, BaseModel) and field_type not in collected:
            collected.add(field_type)
            _collect_nested_types(field_type, collected)

    return collected


def serialization(cls):
    """
    Decorator to recursively process nested Pydantic BaseModel fields in JSON schema.
    Only needs to be applied to the root class.

    Sets all non-default fields as required in the JSON schema,
    and removes fields with exclude=True from both properties and required.

    This decorator uses json_schema_extra mechanism to automatically process
    nested models. Collects all nested types at decoration time and sets
    json_schema_extra on each one.

    Usage:
        @serialization
        class MyModel(BaseModel):
            ...

        schema = MyModel.model_json_schema(mode='serialization')
    """
    if not safe_issubclass(cls, BaseModel):
        raise AttributeError(f'target class {cls.__name__} is not BaseModel')

    # Step 1: Recursively collect all nested Pydantic types
    nested_types = _collect_nested_types(cls)

    # Step 2: Create the json_schema_extra function
    def build():
        def _schema_extra(schema: dict[str, Any], model) -> None:
            # Process exclude fields at current level
            excluded_fields = [k for k, v in model.model_fields.items() if v.exclude]
            props = {}

            for k, v in schema.get('properties', {}).items():
                if k not in excluded_fields:
                    props[k] = v
            schema['properties'] = props

            # Set all non-excluded fields as required
            fnames = list(model.model_fields.keys())
            if excluded_fields:
                fnames = [n for n in fnames if n not in excluded_fields]
            schema['required'] = fnames

        return _schema_extra

    # Step 3: Set json_schema_extra on root class
    cls.model_config['json_schema_extra'] = staticmethod(build())

    # Step 4: Set json_schema_extra on each nested type (if not already set)
    for nested_type in nested_types:
        # Skip if already has json_schema_extra (respect existing config)
        if nested_type.model_config.get('json_schema_extra'):
            continue
        nested_type.model_config['json_schema_extra'] = staticmethod(build())

    return cls
