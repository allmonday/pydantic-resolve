import functools
from dataclasses import is_dataclass
from typing import Type, get_type_hints, List
import pydantic_resolve.constant as const
from pydantic_resolve.compat import PYDANTIC_V2
import pydantic_resolve.utils.class_util as class_util
from pydantic_resolve.analysis import is_acceptable_kls
from pydantic_resolve.utils.types import shelling_type, get_type

from pydantic import BaseModel


def get_class_field_annotations(cls: Type):
    anno = cls.__dict__.get('__annotations__') or {}
    return anno.keys()


def safe_issubclass(kls, classinfo):
    try:
        return issubclass(kls, classinfo)
    except TypeError:
        return False


def rebuild_v1(kls):
    kls.update_forward_refs()

def rebuild_v2(kls):
    kls.model_rebuild()

rebuild = rebuild_v2 if PYDANTIC_V2 else rebuild_v1

def update_forward_refs(kls):
    def update_pydantic_forward_refs(kls: Type[BaseModel]):
        """
        recursively update refs.
        """
        if getattr(kls, const.PYDANTIC_FORWARD_REF_UPDATED, False):
            return

        rebuild(kls)

        setattr(kls, const.PYDANTIC_FORWARD_REF_UPDATED, True)
        
        values = get_values(kls)

        for field in values:
            shelled_type = shelling_type(get_type(field))

            update_forward_refs(shelled_type)

    def update_dataclass_forward_refs(kls):
        if not getattr(kls, const.DATACLASS_FORWARD_REF_UPDATED, False):
            anno = get_type_hints(kls)
            kls.__annotations__ = anno
            setattr(kls, const.DATACLASS_FORWARD_REF_UPDATED, True)

            for _, v in kls.__annotations__.items():
                shelled_type = shelling_type(v)
                update_forward_refs(shelled_type)

    if safe_issubclass(kls, BaseModel):
        update_pydantic_forward_refs(kls)

    if is_dataclass(kls):
        update_dataclass_forward_refs(kls)


def ensure_subset_v1(base):
    """
    used with pydantic class to make sure a class's field is 
    subset of target class
    """
    def wrap(kls):
        assert safe_issubclass(base, BaseModel), 'base should be pydantic class'
        assert safe_issubclass(kls, BaseModel), 'class should be pydantic class'

        @functools.wraps(kls)
        def inner():
            for k, field in kls.__fields__.items():
                if field.required:
                    base_field = base.__fields__.get(k)
                    if not base_field:
                        raise AttributeError(f'{k} not existed in {base.__name__}.')
                    if base_field and base_field.type_ != field.type_:
                        raise AttributeError(f'type of {k} not consistent with {base.__name__}'  )
            return kls
        return inner()
    return wrap


def ensure_subset_v2(base):
    """
    used with pydantic class to make sure a class's field is 
    subset of target class

    for pydantic v2, subclass with Optional[T] but without default value will raise exception

    @class_util.ensure_subset(Base)
    class ChildB1(BaseModel):
        a: str
        d: Optional[int]
    
    this will raise

    @class_util.ensure_subset(Base)
    class ChildB1(BaseModel):
        a: str
        d: Optional[int] = 0 
    
    this is ok
    """
    def wrap(kls):
        assert safe_issubclass(base, BaseModel), 'base should be pydantic class'
        assert safe_issubclass(kls, BaseModel), 'class should be pydantic class'

        @functools.wraps(kls)
        def inner():
            for k, field in kls.model_fields.items():
                if field.is_required():
                    base_field = base.model_fields.get(k)
                    if not base_field:
                        raise AttributeError(f'{k} not existed in {base.__name__}.')
                    if base_field and base_field.annotation != field.annotation:
                        raise AttributeError(f'type of {k} not consistent with {base.__name__}'  )
            return  kls
        return inner()
    return wrap


ensure_subset = ensure_subset_v2 if PYDANTIC_V2 else ensure_subset_v1


def get_kls_full_path(kls):
    return f'{kls.__module__}.{kls.__qualname__}'


def _get_items_v1(kls):
    return kls.__fields__.items()


def _get_items_v2(kls):
    return kls.model_fields.items()


get_items = _get_items_v2 if PYDANTIC_V2 else _get_items_v1


def _get_keys_v1(kls) -> str:
    return kls.__fields__.keys()


def _get_keys_v2(kls) -> str:
    return kls.model_fields.keys()


get_keys = _get_keys_v2 if PYDANTIC_V2 else _get_keys_v1


def _get_values_v1(kls):
    return kls.__fields__.values()


def _get_values_v2(kls):
    return kls.model_fields.values()


get_values = _get_values_v2 if PYDANTIC_V2 else _get_values_v1


def get_pydantic_attrs(kls):
    items = class_util.get_items(kls)

    for name, v in items:
        t = get_type(v)

        shelled_type = shelling_type(t)
        if is_acceptable_kls(shelled_type):
            yield (name, shelled_type)  # type_ is the most inner type


def get_dataclass_attrs(kls):
    for name, v in kls.__annotations__.items():
        shelled_type = shelling_type(v)
        if is_acceptable_kls(shelled_type):
            yield (name, shelled_type)


def get_class(target):
    if isinstance(target, list):
        return target[0].__class__
    else:
        return target.__class__


def _is_required_v1(field):
    return field.required

def _is_required_v2(field):
    return field.is_required()

is_required_field = _is_required_v2 if PYDANTIC_V2 else _is_required_v1