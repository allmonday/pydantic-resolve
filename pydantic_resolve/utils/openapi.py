from typing import Any, Dict
from inspect import isfunction
from dataclasses import is_dataclass
from pydantic import BaseModel
import pydantic_resolve.constant as const
from pydantic_resolve.compat import PYDANTIC_V2
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


def model_config_v1(default_required: bool = True):
    """
    - default_required: 
        if resolve field has default value, it will not be listed in schema['required']
        set default_required=True to add it into required list.
    """
    def _get_pydantic_model(kls):
        if safe_issubclass(kls, BaseModel):
            return kls
        elif hasattr(kls, '__pydantic_model__'):
            return kls.__pydantic_model__
        else:
            raise AttributeError(f'target class {kls.__name__} is not subclass of BaseModel, or decorated by pydantic.dataclass')

    def wrapper(kls):
        pydantic_model = _get_pydantic_model(kls)
        def _schema_extra(schema: Dict[str, Any], model) -> None:
            # define schema.properties
            excludes = set()

            if pydantic_model.__exclude_fields__:
                for k in pydantic_model.__exclude_fields__.keys():
                    excludes.add(k)

            props = {}
            for k, v in schema.get('properties', {}).items():
                if k not in excludes:
                    props[k] = v
            schema['properties'] = props

            # define schema.required
            if default_required:
                fnames = _get_required_fields(model)
                schema['required'] = fnames

        pydantic_model.__config__.schema_extra = staticmethod(_schema_extra)
        return kls
    return wrapper


def model_config_v2(default_required: bool=True):
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
        if is_dataclass(kls):
            return kls
        elif safe_issubclass(kls, BaseModel):
            # TODO: check the behavior of generating json schema in other frameworks using pydantic
            def build():
                def _schema_extra(schema: Dict[str, Any], model) -> None:
                    # 1. collect exclude fields and then hide in both schema and dump (default action)
                    excluded_fields = [k for k, v in kls.model_fields.items() if v.exclude == True]
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
            raise AttributeError(f'target class {kls.__name__} is not BaseModel or dataclass')
    return wrapper


model_config = model_config_v2 if PYDANTIC_V2 else model_config_v1