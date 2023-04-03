import asyncio
import inspect
import contextvars
from inspect import iscoroutine
from typing import TypeVar
from .exceptions import ResolverTargetAttrNotFound
from typing import Any, Callable, Optional
from pydantic_resolve import core
from .constant import PREFIX

def LoaderDepend(  # noqa: N802
    dependency: Optional[Callable[..., Any]] = None 
) -> Any:
    return Depends(dependency=dependency)


class Depends:
    def __init__(
        self, dependency: Optional[Callable[..., Any]] = None
    ):
        self.dependency = dependency

T = TypeVar("T")

class Resolver:
    def __init__(self):
        self.ctx = contextvars.ContextVar('pydantic_resolve_internal_context', default={})
    
    def exec_method(self, method):
        signature = inspect.signature(method)
        params = {}

        for k, v in signature.parameters.items():
            if isinstance(v.default, Depends):
                cache_key = str(v.default.dependency.__name__)
                cache = self.ctx.get()

                hit = cache.get(cache_key, None)
                if hit:
                    instance = hit
                else:
                    instance = v.default.dependency()
                    cache[cache_key] = instance
                    self.ctx.set(cache)

                params[k] = instance
                
        return method(**params)

    async def resolve_obj(self, target, field):
        item = target.__getattribute__(field)
        val = self.exec_method(item)

        if iscoroutine(val):  # async def func()
            val = await val

        if asyncio.isfuture(val):
            val = await val

        val = await self.resolve(val)  

        replace_attr_name = field.replace(PREFIX, '')
        if hasattr(target, replace_attr_name):
            target.__setattr__(replace_attr_name, val)
        else:
            raise ResolverTargetAttrNotFound(f"attribute {replace_attr_name} not found")

    async def resolve(self, target: T) -> T:
        """ entry: resolve dataclass object or pydantic object / or list in place """

        if isinstance(target, (list, tuple)):
            await asyncio.gather(*[self.resolve(t) for t in target])

        if core._is_acceptable_type(target):
            await asyncio.gather(*[self.resolve_obj(target, field) 
                                   for field in core._iter_over_object_resolvers(target)])

        return target