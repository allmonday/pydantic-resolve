import functools
from typing import Type, List, Tuple, Iterator
import pydantic_resolve.constant as const
import pydantic_resolve.utils.class_util as class_util
from pydantic_resolve.analysis import is_acceptable_kls
from pydantic_resolve.utils.er_diagram import LoaderInfo
from pydantic_resolve.utils.types import get_type, get_core_types
from pydantic import BaseModel

def rebuild(kls):
    kls.model_rebuild()


def ensure_subset(base):
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
        is_base_pydantic = safe_issubclass(base, BaseModel)
        is_kls_pydantic = safe_issubclass(kls, BaseModel)

        setattr(kls, const.ENSURE_SUBSET_REFERENCE, base)

        if is_base_pydantic and is_kls_pydantic:
            @functools.wraps(kls)
            def inner():
                for k, field in kls.model_fields.items():
                    if field.is_required():
                        base_field = base.model_fields.get(k)
                        if not base_field:
                            raise AttributeError(f'{k} not existed in {base.__name__}.')
                        if base_field and base_field.annotation != field.annotation:
                            raise AttributeError(f'type of {k} not consistent with {base.__name__}')
                return kls
            return inner()
        else:
            raise TypeError('base and kls should both be Pydantic BaseModel')
    return wrap


def get_pydantic_field_items(kls):
    return kls.model_fields.items()


def get_pydantic_field_keys(kls) -> str:
    return kls.model_fields.keys()


def get_pydantic_field_items_with_load_by(kls) -> Iterator[Tuple[str, LoaderInfo]]:
    """
    find fields which have LoadBy metadata.

    example:

    class Base(BaseModel):
        id: int
        name: str
        b_id: int
    
    class B(BaseModel):
        id: int
        name: str

    class A(Base):
        b: Annotated[Optional[B], LoadBy('b_id')] = None
        extra: str = ''
    
    return ('b', LoadBy('b_id'))
    """
    items = kls.model_fields.items()

    for name, v in items:
        metadata = v.metadata
        for meta in metadata:
            if isinstance(meta, LoaderInfo):
                yield name, meta 


def get_pydantic_field_values(kls):
    return kls.model_fields.values()


def is_pydantic_field_required_field(field):
    return field.is_required()


def get_pydantic_fields(kls):
    items = class_util.get_pydantic_field_items(kls)

    for name, v in items:
        t = get_type(v)
        shelled_types = get_core_types(t)
        allowed_types = [st for st in shelled_types if is_acceptable_kls(st)]
        if allowed_types:
            yield (name, allowed_types)  # type_ is the most inner type


def get_class_of_object(target):
    if isinstance(target, list):
        return target[0].__class__
    else:
        return target.__class__


def update_forward_refs(kls):
    def update_pydantic_forward_refs(kls: Type[BaseModel]):
        """
        recursively update refs.
        """
        if getattr(kls, const.PYDANTIC_FORWARD_REF_UPDATED, False):
            return

        rebuild(kls)

        setattr(kls, const.PYDANTIC_FORWARD_REF_UPDATED, True)
        
        values = get_pydantic_field_values(kls)

        for field in values:
            shelled_types = get_core_types(get_type(field))
            for shelled_type in shelled_types:
                update_forward_refs(shelled_type)

    if safe_issubclass(kls, BaseModel):
        update_pydantic_forward_refs(kls)


def get_kls_full_name(kls):
    return f'{kls.__module__}.{kls.__qualname__}'


def get_fields_default_value_not_provided(cls: Type) -> List[Tuple[str, bool]]:  # field name, has default value
    """
    return class field which do not have a default value.

    class MyClass:
        a: int
        b: int = 1

    print(hasattr(MyClass, 'a'))  # False
    print(hasattr(MyClass, 'b'))  # True
    """
    anno = cls.__dict__.get('__annotations__') or {}
    return [(k, hasattr(cls, k)) for k in anno.keys()]


def safe_issubclass(kls, classinfo):
    try:
        return issubclass(kls, classinfo)
    except TypeError:
        return False