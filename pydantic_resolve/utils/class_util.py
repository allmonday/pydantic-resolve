import functools
from typing import Type, List, Tuple, Iterator, get_origin, get_args
import pydantic_resolve.constant as const
import pydantic_resolve.utils.class_util as class_util
from pydantic_resolve.analysis import is_acceptable_kls
from pydantic_resolve.utils.er_diagram import LoaderInfo
from pydantic_resolve.utils.types import get_type, get_core_types
from pydantic import BaseModel


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


def get_pydantic_field_items_with_load_by(kls) -> Iterator[Tuple[str, LoaderInfo, Type]]:
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
                yield name, meta, v.annotation 


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
    def update_pydantic_forward_refs(pydantic_kls: type[BaseModel]):
        """
        recursively update refs.
        """

        pydantic_kls.model_rebuild()
        setattr(pydantic_kls, const.PYDANTIC_FORWARD_REF_UPDATED, True)

        values = pydantic_kls.model_fields.values()
        for field in values:
            update_forward_refs(field.annotation)
        
    for shelled_type in get_core_types(kls):
        # Only treat as updated if the flag is set on the class itself, not via inheritance
        local_attrs = getattr(shelled_type, '__dict__', {})
        if local_attrs.get(const.PYDANTIC_FORWARD_REF_UPDATED, False):
            continue

        if safe_issubclass(shelled_type, BaseModel):
            update_pydantic_forward_refs(shelled_type)


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
    

def is_compatible_type(src_type, target_type) -> bool:
    """
    1. try to shell optional in src_type and then compare with target_type
    2. if src_type is a subset of target_type, or subset of subset (visit recursively until find), return True
    3. if src_type is subclass of target_type, or subclass of subclass (visit recursively until find), return True
    4. Union and UnionType is not compatible
    """
    # Helper: unwrap Optional[X] in source type only
    def unwrap_optional(tp):
        origin = get_origin(tp)
        if origin is None:
            return tp
        # typing.Union and PEP604 (types.UnionType) both have origin of Union/UnionType
        if str(origin) in {"typing.Union", "types.UnionType"}:
            args = [a for a in get_args(tp) if a is not type(None)]
            if len(args) == 1:
                return args[0]
        return tp

    # Helper: detect any non-optional union
    def is_union(tp):
        origin = get_origin(tp)
        return str(origin) in {"typing.Union", "types.UnionType"}

    # Helper: subset ancestry check via ENSURE_SUBSET_REFERENCE chain
    def is_subset_of(src, tgt) -> bool:
        current = src
        while current is not None:
            if current is tgt:
                return True
            current = getattr(current, const.ENSURE_SUBSET_REFERENCE, None)
        return False

    # Helper: list element compatibility
    def is_list_compatible(src, tgt) -> bool:
        src_origin, tgt_origin = get_origin(src), get_origin(tgt)
        if src_origin is list and tgt_origin is list:
            src_args, tgt_args = get_args(src), get_args(tgt)
            if not src_args or not tgt_args:
                return False
            return is_compatible_type(src_args[0], tgt_args[0])
        return False

    # 1) unwrap Optional in src_type
    src = unwrap_optional(src_type)
    tgt = target_type

    # 4) unions (other than Optional case already unwrapped) are incompatible
    if is_union(src) or is_union(tgt):
        return False

    # 3) handle list generics (typing.List and built-in list share origin list)
    if is_list_compatible(src, tgt):
        return True

    # Direct equality
    if src is tgt:
        return True

    # 2) subset chain match
    try:
        if is_subset_of(src, tgt):
            return True
    except Exception:
        pass

    # 3) subclass chain
    try:
        if safe_issubclass(src, tgt):
            return True
    except Exception:
        pass

    return False
