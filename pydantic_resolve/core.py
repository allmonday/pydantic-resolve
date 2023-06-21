import asyncio
from inspect import ismethod, iscoroutine
from pydantic import BaseModel
from dataclasses import is_dataclass
from typing import TypeVar
from .exceptions import ResolverTargetAttrNotFound, DataloaderDependCantBeResolved
from .constant import PREFIX, POST_PREFIX

T = TypeVar("T")

def is_acceptable_type(target):
    """
    Check whether target is Pydantic object or Dataclass object

    :param target: object
    :type target: BaseModel or Dataclass 
    :rtype: bool

    """
    return isinstance(target, BaseModel) or is_dataclass(target)

def iter_over_object_resolvers(target):
    """get method starts with resolve_"""
    for k in dir(target):
        if k.startswith(PREFIX) and ismethod(target.__getattribute__(k)):
            yield k

def iter_over_object_post_methods(target):
    """get method starts with post_"""
    for k in dir(target):
        if k.startswith(POST_PREFIX) and ismethod(target.__getattribute__(k)):
            yield k

async def resolve_obj(target, field):
    """
    TODO: deprecated, will remove in v2.0
    """
    item = target.__getattribute__(field)
    try:
        val = item()
    except AttributeError as e:
        if str(e) == "'Depends' object has no attribute 'load'":  
            raise DataloaderDependCantBeResolved("DataLoader used in schema, use Resolver().resolve() instead")
        raise e

    while iscoroutine(val) or asyncio.isfuture(val):
        val = await val

    val = await resolve(val)  

    replace_attr_name = field.replace(PREFIX, '')
    if hasattr(target, replace_attr_name):
        target.__setattr__(replace_attr_name, val)
    else:
        raise ResolverTargetAttrNotFound(f"attribute {replace_attr_name} not found")

async def resolve(target: T) -> T:
    """ 
    entry: resolve dataclass object or pydantic object / or list in place 
    TODO: deprecated, will remove in v2.0
    """

    if isinstance(target, (list, tuple)):  # core/test_1, 3
        await asyncio.gather(*[resolve(t) for t in target])

    if is_acceptable_type(target):
        await asyncio.gather(*[resolve_obj(target, field) 
                               for field in iter_over_object_resolvers(target)])

    return target