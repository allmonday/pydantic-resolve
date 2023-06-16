import functools
from typing import DefaultDict, Type, TypeVar, List, Callable, Optional, Mapping
from collections import defaultdict

def get_class_field_annotations(cls: Type):
    anno = cls.__dict__.get('__annotations__') or {}
    return anno.keys()


T = TypeVar("T")
V = TypeVar("V")

def build_object(items: List[T], keys: List[V], get_pk: Callable[[T], V]) -> List[Optional[T]]:
    """
    helper function to build return object data required by aiodataloader
    """
    dct: Mapping[V, T] = {}
    for item in items:
        _key = get_pk(item)
        dct[_key] = item
    results = [dct.get(k, None) for k in keys]
    return results


def build_list(items: List[T], keys: List[V], get_pk: Callable[[T], V]) -> List[List[T]]:
    """
    helper function to build return list data required by aiodataloader
    """
    dct: DefaultDict[V, List[T]] = defaultdict(list) 
    for item in items:
        _key = get_pk(item)
        dct[_key].append(item)
    results = [dct.get(k, []) for k in keys]
    return results


def transformer_decorator(func: Callable):
    def inner(fn):
        @functools.wraps(fn)
        async def wrap(*args, **kwargs):
            items = await fn(*args, **kwargs)
            items = [func(item) for item in items]
            return items
        return wrap
    return inner


def replace_method(cls: Type, cls_name: str, func_name: str, func: Callable):
    KLS = type(cls_name, (cls,), {func_name: func})
    return KLS
