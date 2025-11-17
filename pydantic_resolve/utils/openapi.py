from typing import Any, Dict
from inspect import isfunction
from pydantic import BaseModel
import pydantic_resolve.constant as const
from pydantic_resolve.utils.class_util import safe_issubclass, is_pydantic_field_required_field, get_pydantic_field_items


def _get_required_fields(kls: BaseModel):
    required_fields = []

    items = get_pydantic_field_items(kls)

    for fname, field in items:
        if is_pydantic_field_required_field(field):
            required_fields.append(fname)


    # 2. get resolve_ and post_ target fields
    for f in dir(kls):
        if f.startswith(const.RESOLVE_PREFIX):
            if isfunction(getattr(kls, f)):
                required_fields.append(f.replace(const.RESOLVE_PREFIX, ''))

        if f.startswith(const.POST_PREFIX):
            if isfunction(getattr(kls, f)):
                required_fields.append(f.replace(const.POST_PREFIX, ''))

    return required_fields


def model_config(default_required: bool=True):
    """
    in pydantic v2, we can not use __exclude_field__ to set hidden field in model_config hidden_field params
    model_config now is just a simple decorator to remove fields (with exclude=True) from schema.properties
    and set schema.required for better schema description. 
    (same like `output` decorator, you can replace output with model_config)

    it keeps the form of model_config(params) in order to extend new features in future

    update:

    in fastapi + pydantic v2, this function will be handled internal automatically with mode: serilization
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
                        fnames = _get_required_fields(model)
                        if excluded_fields:
                            fnames = [n for n in fnames if n not in excluded_fields]
                        schema['required'] = fnames

                return _schema_extra

            kls.model_config['json_schema_extra'] = staticmethod(build())
            return kls
        else:
            raise AttributeError(f'target class {kls.__name__} is not BaseModel')
    return wrapper

