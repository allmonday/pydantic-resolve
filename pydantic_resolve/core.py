import asyncio
from inspect import ismethod, iscoroutine
from pydantic import BaseModel
from dataclasses import is_dataclass, fields as dc_fields
from typing import TypeVar
from .exceptions import ResolverTargetAttrNotFound, DataloaderDependCantBeResolved
from .constant import PREFIX, POST_PREFIX, RESOLVER, ATTRIBUTE

T = TypeVar("T")

def is_list(target) -> bool:
    return isinstance(target, (list, tuple))

def is_acceptable_type(target):
    """
    Check whether target is Pydantic object or Dataclass object

    :param target: object
    :type target: BaseModel or Dataclass 
    :rtype: bool

    """
    return isinstance(target, BaseModel) or is_dataclass(target)


def iter_over_object_resolvers_and_acceptable_fields(target):
    """
        return 
        1. method starts with resolve_,  eg: resolve_name, resolve_age
        2. field of pydantic or dataclass, which is not resolved by step1. (if `resolve_name` already exists, it will skip `name` )
    """
    resolver_fields = set()
    fields = dir(target)
    resolvers = [f for f in fields if f.startswith(PREFIX)]

    if isinstance(target, BaseModel):
        attributes = list(target.__fields__.keys())
    elif is_dataclass(target):
        attributes = [f.name for f in dc_fields(target)]
    else:
        raise AttributeError('invalid type: should be pydantic object or dataclass object')  # noqa

    for field in resolvers:
        attr = target.__getattribute__(field)
        if ismethod(attr):
            resolver_fields.add(field.replace(PREFIX, ''))
            yield (field, attr, RESOLVER)

    for field in attributes: 
        if (field in resolver_fields):  # skip field of resolve_[field]
            continue
        attr = target.__getattribute__(field)
        if is_acceptable_type(attr) or is_list(attr):
            yield (field, attr,ATTRIBUTE)

def iter_over_object_post_methods(target):
    """get method starts with post_"""
    for k in dir(target):
        if k.startswith(POST_PREFIX) and ismethod(target.__getattribute__(k)):
            yield k
