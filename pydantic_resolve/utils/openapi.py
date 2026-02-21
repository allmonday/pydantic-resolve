from typing import Any, Dict, Union, get_origin, get_args
from pydantic import BaseModel
from pydantic_resolve.utils.class_util import safe_issubclass


def model_config(default_required: bool=True):
    """
    in pydantic v2, we can not use __exclude_field__ to set hidden field in model_config hidden_field params
    model_config now is just a simple decorator to remove fields (with exclude=True) from schema.properties
    and set schema.required for better schema description. 
    (same like `output` decorator, you can replace output with model_config)

    it keeps the form of model_config(params) in order to extend new features in future

    update:

    in fastapi + pydantic v2, this function will be handled internal automatically with mode: serialization
    you can remove the model_config_v2

    reference: fastapi/_compat.py::get_definitions
    """
    def wrapper(kls):
        if safe_issubclass(kls, BaseModel):
            # TODO: check the behavior of generating json schema in other frameworks using pydantic
            def build():
                def _schema_extra(schema: Dict[str, Any], model) -> None:
                    # 1. collect exclude fields and then hide in both schema and dump (default action)
                    excluded_fields = [k for k, v in kls.model_fields.items() if v.exclude]
                    props = {}

                    # config schema properties
                    for k, v in schema.get('properties', {}).items():
                        if k not in excluded_fields:
                            props[k] = v
                    schema['properties'] = props

                    # config schema required (fields with default values will not be listed in required field)
                    # and the generated typescript models will define it as optional, and is troublesome in use
                    if default_required:
                        fnames = list(model.model_fields.keys())
                        if excluded_fields:
                            fnames = [n for n in fnames if n not in excluded_fields]
                        schema['required'] = fnames

                return _schema_extra

            kls.model_config['json_schema_extra'] = staticmethod(build())
            return kls
        else:
            raise AttributeError(f'target class {kls.__name__} is not BaseModel')
    return wrapper


def serialization():
    """
    Similar to model_config, but recursively processes nested Pydantic BaseModel fields.
    Only needs to be applied to the root class.

    Sets all non-default fields as required in the JSON schema,
    and removes fields with exclude=True from both properties and required.

    Note: This decorator wraps model_json_schema() to automatically process nested models.
    Use mode='serialization' for proper handling of exclude=True fields.

    Usage:
        @serialization()
        class MyModel(BaseModel):
            ...

        schema = MyModel.model_json_schema(mode='serialization')
    """
    def wrapper(kls):
        if safe_issubclass(kls, BaseModel):
            # Store original model_json_schema method
            original_method = kls.model_json_schema

            def wrapped_model_json_schema(*args, **kwargs):
                """Wrapper that auto-processes nested models after schema generation"""
                schema = original_method(*args, **kwargs)
                # Post-process to handle nested models
                _process_schema(schema, kls)
                return schema

            kls.model_json_schema = wrapped_model_json_schema
            return kls
        else:
            raise AttributeError(f'target class {kls.__name__} is not BaseModel')
    return wrapper


def _process_schema(schema: Dict[str, Any], model):
    """Recursively process schema for nested models"""
    # 1. Process exclude fields at current level
    excluded_fields = [k for k, v in model.model_fields.items() if v.exclude]
    props = {}

    for k, v in schema.get('properties', {}).items():
        if k not in excluded_fields:
            props[k] = v
    schema['properties'] = props

    # 2. Set required fields (default all as required)
    fnames = list(model.model_fields.keys())
    if excluded_fields:
        fnames = [n for n in fnames if n not in excluded_fields]
    schema['required'] = fnames

    # 3. Recursively process nested BaseModel fields
    for field_name, field_info in model.model_fields.items():
        if field_name in excluded_fields:
            continue

        # Get field type
        field_type = field_info.annotation
        if field_type is None:
            continue

        # Get the origin (list, Union, etc.)
        origin = get_origin(field_type)

        # Handle List[SomeModel] case
        if origin is list:
            args = get_args(field_type)
            if args:
                nested_type = args[0]
                _process_nested_type(schema, field_name, nested_type)
        # Handle Union[SomeModel, None] or SomeModel | None case
        # Check for both typing.Union and types.UnionType (Python 3.10+)
        elif origin is Union or (origin is not None and getattr(origin, '__name__', None) == 'UnionType'):
            args = get_args(field_type)
            if args:
                # Find the non-None type in the Union
                for arg in args:
                    if arg is not type(None):
                        _process_nested_type(schema, field_name, arg)
                        break
        # Handle SomeModel case
        elif safe_issubclass(field_type, BaseModel):
            _process_nested_type(schema, field_name, field_type)


def _process_nested_type(schema, field_name, nested_type):
    """Process nested model type"""
    if field_name not in schema.get('properties', {}):
        return

    prop_schema = schema['properties'][field_name]

    # Handle Optional[Model] which generates anyOf/oneOf with $ref
    for wrapper_key in ['anyOf', 'oneOf', 'allOf']:
        if wrapper_key in prop_schema:
            for item in prop_schema[wrapper_key]:
                if isinstance(item, dict) and '$ref' in item:
                    _process_reference(item['$ref'], schema, nested_type)
            return

    # Handle direct $ref
    nested_schema = prop_schema.get('$ref', '')
    if nested_schema:
        _process_reference(nested_schema, schema, nested_type)


def _process_reference(ref_path, schema, nested_type):
    """Process a $ref reference to find and process the nested model"""
    # Get ref name from $ref
    ref_name = ref_path.split('/')[-1]
    definitions = schema.get('$defs', {})

    # Try to find the matching definition by name
    target_def = None
    nested_name = nested_type.__name__

    # First try exact match
    if ref_name in definitions:
        target_def = definitions[ref_name]
    else:
        # Try to find by class name (pydantic may mangle the name)
        for key, value in definitions.items():
            if key.endswith(nested_name) or nested_name in key:
                target_def = value
                break

    if target_def:
        # Recursively process
        _process_schema(target_def, nested_type)
