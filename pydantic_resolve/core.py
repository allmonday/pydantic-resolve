import asyncio
from inspect import ismethod, iscoroutine
from pydantic import BaseModel
from dataclasses import is_dataclass
from typing import TypeVar
from .exceptions import ResolverTargetAttrNotFound, DataloaderDependCantBeResolved
from .constant import PREFIX

T = TypeVar("T")

def _is_acceptable_type(target):
    return isinstance(target, BaseModel) or is_dataclass(target)

def _iter_over_object_resolvers(target):
    """get method starts with resolve_"""
    for k in dir(target):
        if k.startswith(PREFIX) and ismethod(target.__getattribute__(k)):
            yield k

async def resolve_obj(target, field):
    item = target.__getattribute__(field)
    try:
        val = item()
    except AttributeError as e:
        if str(e) == "'Depends' object has no attribute 'load'":  
            # TODO: str(e) may changes in future, not stable
            raise DataloaderDependCantBeResolved("DataLoader used in schema, use Resolver().resolve() instead")
        raise e

    if iscoroutine(val):  # async def func()
        val = await val

    if asyncio.isfuture(val):
        val = await val

    val = await resolve(val)  

    replace_attr_name = field.replace(PREFIX, '')
    if hasattr(target, replace_attr_name):
        target.__setattr__(replace_attr_name, val)
    else:
        raise ResolverTargetAttrNotFound(f"attribute {replace_attr_name} not found")

async def resolve(target: T) -> T:
    """ entry: resolve dataclass object or pydantic object / or list in place """

    if isinstance(target, (list, tuple)):  # core/test_1, 3
        await asyncio.gather(*[resolve(t) for t in target])

    if _is_acceptable_type(target):
        await asyncio.gather(*[resolve_obj(target, field) 
                               for field in _iter_over_object_resolvers(target)])

    return target