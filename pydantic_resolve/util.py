import asyncio
from inspect import ismethod, iscoroutine
from pydantic import BaseModel
from dataclasses import is_dataclass
from typing import TypeVar, Union, List

T = TypeVar("T")

PREFIX = 'resolve_'

def _is_acceptable_type(target):
    return isinstance(target, BaseModel) or is_dataclass(target)

def _iter_over_object_resolvers(target):
    """get method starts with resolve_"""
    for k in dir(target):
        if k.startswith(PREFIX):
            yield k

async def resolve(target: Union[T, List[T]]) -> Union[T, List[T]]:
    """ resolve dataclass object or pydantic object """

    if isinstance(target, (list, tuple)):
        results = await asyncio.gather(*[resolve(t) for t in target])
        return results

    if _is_acceptable_type(target):
        for k in _iter_over_object_resolvers(target):
            item = target.__getattribute__(k)

            if ismethod(item):  # instance method
                val = item()

                if iscoroutine(val):
                    """
                    async def resolve_xxx(self):
                        return ...
                    """
                    val = await val

                if asyncio.isfuture(val):  # is future
                    """
                    def resolve_xxx(self):
                        return asyncio.Future()
                    """
                    val = await val

                val = await resolve(val)  
                target.__setattr__(k.replace(PREFIX, ''), val)

    return target