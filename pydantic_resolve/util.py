import asyncio
from collections import defaultdict
from dataclasses import is_dataclass
import functools
from pydantic import BaseModel
from inspect import iscoroutine
from typing import DefaultDict, Sequence, Type, TypeVar, List, Callable, Optional, Mapping, Union
import types

def get_class_field_annotations(cls: Type):
    anno = cls.__dict__.get('__annotations__') or {}
    return anno.keys()


T = TypeVar("T")
V = TypeVar("V")

def build_object(items: Sequence[T], keys: List[V], get_pk: Callable[[T], V]) -> List[Optional[T]]:
    """
    helper function to build return object data required by aiodataloader
    """
    dct: Mapping[V, T] = {}
    for item in items:
        _key = get_pk(item)
        dct[_key] = item
    results = [dct.get(k, None) for k in keys]
    return results


def build_list(items: Sequence[T], keys: List[V], get_pk: Callable[[T], V]) -> List[List[T]]:
    """
    helper function to build return list data required by aiodataloader
    """
    dct: DefaultDict[V, List[T]] = defaultdict(list) 
    for item in items:
        _key = get_pk(item)
        dct[_key].append(item)
    results = [dct.get(k, []) for k in keys]
    return results


def replace_method(cls: Type, cls_name: str, func_name: str, func: Callable):
    KLS = type(cls_name, (cls,), {func_name: func})
    return KLS


def mapper(func_or_class: Union[Callable, Type]):
    """
    execute post-transform function after the value is reolved
    func_or_class:
        is func: run func
        is class: call auto_mapping to have a try
    """
    def inner(inner_fn):
        @functools.wraps(inner_fn)
        async def wrap(*args, **kwargs):

            val = inner_fn(*args, **kwargs)
            while iscoroutine(val) or asyncio.isfuture(val):
                val = await val
            
            if val is None:
                return None

            if isinstance(func_or_class, types.FunctionType):
                return func_or_class(val)
            else:
                if isinstance(val, list):
                    return [auto_mapping(func_or_class, v) for v in val]
                return auto_mapping(func_or_class, val)
        return wrap
    return inner


def auto_mapping(target, source):
    # do noting
    if isinstance(source, target):
        return source

    try:
        # pydantic
        if issubclass(target, BaseModel):
            if target.Config.orm_mode:
                return target.from_orm(source)
            return target.parse_obj(source)
        
        # dataclass
        if is_dataclass(target):
            if isinstance(source, dict):
                return target(**source)

    except Exception as e:
        raise e
    
    raise RuntimeError('auto mapping fails')