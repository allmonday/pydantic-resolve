import asyncio
from inspect import ismethod, iscoroutine
from pydantic import BaseModel
from dataclasses import is_dataclass
from typing import TypeVar, Union, List

T = TypeVar("T")

def _iter_object(target):
    if isinstance(target, BaseModel):
        keys = target.__fields_set__
        for k in dir(target):
            if k in keys:  # attr
                yield k
            if k.startswith('resolve_'):  # methods
                yield k

    elif is_dataclass(target):
        for k in dir(target):
            if not k.startswith('__'):  # attrs and methods
                yield k


async def resolve(target: Union[T, List[T]]) -> Union[T, List[T]]:
    """ resolve dataclass object or pydantic object """

    if isinstance(target, list):
        results = await asyncio.gather(*[resolve(t) for t in target])
        return results

    for k in _iter_object(target):
        item = target.__getattribute__(k)

        if ismethod(item):  # instance method
            val = item()

            if iscoroutine(val):
                val = await val

            if asyncio.isfuture(val):  # is future
                val = await val  # get value from future
                val = await resolve(val)

            target.__setattr__(k.replace('resolve_', ''), val)

    return target
