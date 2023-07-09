import asyncio
import inspect
import contextvars
from inspect import iscoroutine
from typing import TypeVar, Dict
from .exceptions import ResolverTargetAttrNotFound, LoaderFieldNotProvidedError, MissingAnnotationError
from typing import Any, Callable, Optional
from pydantic_resolve import core
from .constant import HAS_MAPPER_FUNCTION, PREFIX, POST_PREFIX, ATTRIBUTE, RESOLVER
from .util import get_class_field_annotations, try_parse_data_to_target_field_type
from inspect import isclass
from aiodataloader import DataLoader


def LoaderDepend(  # noqa: N802
    dependency: Optional[Callable[..., Any]] = None,
) -> Any:
    return Depends(dependency=dependency)

class Depends:
    def __init__(
        self, 
        dependency: Optional[Callable[..., Any]] = None,
    ):
        self.dependency = dependency

T = TypeVar("T")

class Resolver:
    """
    Entrypoint of a resolve action
    """
    def __init__(
            self, 
            loader_filters: Optional[Dict[Any, Dict[str, Any]]] = None, 
            loader_instances: Optional[Dict[Any, Any]] = None,
            ensure_type=False):
        self.ctx = contextvars.ContextVar('pydantic_resolve_internal_context', default={})

        # for dataloader which has class attributes, you can assign the value at here
        self.loader_filters_ctx = contextvars.ContextVar('pydantic_resolve_internal_filter', default=loader_filters or {})

        # now you can pass your loader instance, Resolver will check isinstance
        if loader_instances and self.validate_instance(loader_instances):
            self.loader_instances = loader_instances
        else:
            self.loader_instances = None

        self.ensure_type = ensure_type
    
    def validate_instance(self, loader_instances: Dict[Any, Any]):
        for cls, loader in loader_instances.items():
            if not issubclass(cls, DataLoader):
                raise AttributeError(f'{cls.__name__} must be subclass of DataLoader')
            if not isinstance(loader, cls):
                raise AttributeError(f'{loader.__name__} is not instance of {cls.__name__}')
        return True

    def exec_method(self, method):
        signature = inspect.signature(method)
        params = {}

        # manage the creation of loader instances
        for k, v in signature.parameters.items():
            if isinstance(v.default, Depends):
                # Base: DataLoader or batch_load_fn
                Base = v.default.dependency

                # check loader_instance first, if has predefined loader instance, just use it.
                if self.loader_instances and self.loader_instances.get(Base):
                    loader = self.loader_instances.get(Base)
                    params[k] = loader
                    continue

                # module.kls to avoid same kls name from different module
                cache_key = f'{v.default.dependency.__module__}.{v.default.dependency.__name__}'
                cache_provider = self.ctx.get()
                hit = cache_provider.get(cache_key, None)
                if hit:
                    loader = hit
                else:
                    # create loader instance 
                    if isclass(Base):
                        # if extra transform provides
                        loader = Base()

                        # and pick config from 'loader_filters' param, only for DataClass
                        filter_config_provider = self.loader_filters_ctx.get()
                        filter_config = filter_config_provider.get(Base, {})

                        # class ExampleLoader(DataLoader):
                        #     filtar_x: bool  <--------------- set this field

                        for field in get_class_field_annotations(Base):
                            try:
                                value = filter_config[field]
                                setattr(loader, field, value)
                            except KeyError:
                                raise LoaderFieldNotProvidedError(f'{cache_key}.{field} not found in Resolver()')

                    # build loader from batch_load_fn, filters config is impossible
                    else:
                        loader = DataLoader(batch_load_fn=Base) # type:ignore

                    cache_provider[cache_key] = loader
                    self.ctx.set(cache_provider)
                params[k] = loader
        return method(**params)


    async def resolve_obj_field(self, target, field, attr):
        target_attr_name = str(field).replace(PREFIX, '')

        if not hasattr(target, target_attr_name):
            raise ResolverTargetAttrNotFound(f"attribute {target_attr_name} not found")

        if self.ensure_type:
            if not attr.__annotations__:
                raise MissingAnnotationError(f'{field}: return annotation is required')

        val = self.exec_method(attr)
        while iscoroutine(val) or asyncio.isfuture(val):
            val = await val

        val = await self.resolve(val)  

        if not getattr(attr, HAS_MAPPER_FUNCTION, False):  # defined in util.mapper
            val = try_parse_data_to_target_field_type(target, target_attr_name, val)
        target.__setattr__(target_attr_name, val)


    async def resolve(self, target: T) -> T:
        """ entry: resolve dataclass object or pydantic object / or list in place """
        if isinstance(target, (list, tuple)):
            await asyncio.gather(*[self.resolve(t) for t in target])

        if core.is_acceptable_type(target):
            tasks = []
            for field, attr, _type in core.iter_over_object_resolvers_and_acceptable_fields(target):
                if _type == ATTRIBUTE: tasks.append(self.resolve(attr))
                if _type == RESOLVER: tasks.append(self.resolve_obj_field(target, field, attr))

            await asyncio.gather(*tasks)

            # execute post methods, take no params
            for post_key in core.iter_over_object_post_methods(target):
                post_attr_name = post_key.replace(POST_PREFIX, '')
                if not hasattr(target, post_attr_name):
                    raise ResolverTargetAttrNotFound(f"fail to run {post_key}(), attribute {post_attr_name} not found")

                post_method = target.__getattribute__(post_key)
                post_method()

        return target