import asyncio
import contextvars
import warnings
from inspect import iscoroutine
from typing import TypeVar, Dict
from .exceptions import MissingAnnotationError
from typing import Any, Optional
from pydantic_resolve import core
from aiodataloader import DataLoader
from types import MappingProxyType
import pydantic_resolve.constant as const
import pydantic_resolve.util as util


T = TypeVar("T")

class Resolver:
    def __init__(
            self,
            loader_filters: Optional[Dict[Any, Dict[str, Any]]] = None,  # deprecated
            loader_params: Optional[Dict[Any, Dict[str, Any]]] = None,
            global_loader_filter: Optional[Dict[str, Any]] = None,  # deprecated
            global_loader_param: Optional[Dict[str, Any]] = None,
            loader_instances: Optional[Dict[Any, Any]] = None,
            ensure_type=False,
            context: Optional[Dict[str, Any]] = None):
        self.loader_instance_cache = {}

        self.ancestor_vars = {}
        self.collector_contextvars = {}
        self.parent_contextvars = {}

        # for dataloader which has class attributes, you can assign the value at here
        if loader_filters:
            warnings.warn('loader_filters is deprecated, use loader_params instead.', DeprecationWarning)
            self.loader_params = loader_filters
        else:
            self.loader_params = loader_params or {}

        # keys in global_loader_filter are mutually exclusive with key-value pairs in loader_filters
        # eg: Resolver(global_loader_filter={'key_a': 1}, loader_filters={'key_a': 1}) will raise exception
        if global_loader_filter:
            warnings.warn('global_loader_filter is deprecated, use global_loader_param instead.', DeprecationWarning)
            self.global_loader_param = global_loader_filter or {}
        else:
            self.global_loader_param = global_loader_param or {}

        # now you can pass your loader instance, Resolver will check `isinstance``
        if loader_instances and self._validate_loader_instance(loader_instances):
            self.loader_instances = loader_instances
        else:
            self.loader_instances = {}

        self.ensure_type = ensure_type
        self.context = MappingProxyType(context) if context else None
        self.metadata = {}
        self.object_collect_alias_map_store = {}

    def _validate_loader_instance(self, loader_instances: Dict[Any, Any]):
        for cls, loader in loader_instances.items():
            if not issubclass(cls, DataLoader):
                raise AttributeError(f'{cls.__name__} must be subclass of DataLoader')
            if not isinstance(loader, cls):
                raise AttributeError(f'{loader.__name__} is not instance of {cls.__name__}')
        return True
    
    def _prepare_collectors(self, target, kls):
        alias_map = core.get_collectors(kls, self.metadata)
        if alias_map:
            self.object_collect_alias_map_store[id(target)] = alias_map

            for alias, sign_collector_pair in alias_map.items():
                if not self.collector_contextvars.get(alias):
                    self.collector_contextvars[alias] = contextvars.ContextVar(alias, default={})
                
                current_pair = self.collector_contextvars[alias].get()
                updated_pair = {**current_pair, **sign_collector_pair}
                self.collector_contextvars[alias].set(updated_pair)

    def _add_values_into_collectors(self, target, kls):
        for field, alias in core.iter_over_collectable_fields(kls, self.metadata):
            # handle two scenarios
            # {'name': ('collector_a', 'collector_b')}
            # {'name': 'collector_a'}
            alias_list = alias if isinstance(alias, (tuple, list)) else (alias,)

            for alias in alias_list:
                for _, instance in self.collector_contextvars[alias].get().items():
                    val = [getattr(target, f) for f in field]\
                        if isinstance(field, tuple) else getattr(target, field)
                    instance.add(val)
    
    def _add_parent(self, target):
        if not self.parent_contextvars.get('parent'):
            self.parent_contextvars['parent'] = contextvars.ContextVar('parent')
        self.parent_contextvars['parent'].set(target)

    def _add_expose_fields(self, target):
        expose_dict: Optional[dict] = getattr(target, const.EXPOSE_TO_DESCENDANT, None)
        if expose_dict:
            for field, alias in expose_dict.items():  # eg: {'name': 'bar_name'}
                if not self.ancestor_vars.get(alias):
                    self.ancestor_vars[alias] = contextvars.ContextVar(alias)

                try:
                    val = getattr(target, field)
                except AttributeError:
                    raise AttributeError(f'{field} does not existed')

                self.ancestor_vars[alias].set(val)

    def _prepare_ancestor_context(self):
        return {k: v.get() for k, v in self.ancestor_vars.items()}

    def _execute_resolver_method(self, kls, field, method):
        params = {}
        resolve_param = core.get_resolve_param(kls, field, self.metadata)
        if resolve_param['context']:
            params['context'] = self.context
        if resolve_param['ancestor_context']:
            params['ancestor_context'] = self._prepare_ancestor_context()
        if resolve_param['parent']:
            params['parent'] = self.parent_contextvars['parent'].get()
        
        for loader in resolve_param['dataloaders']:
            cache_key = loader['path']
            loader_instance = self.loader_instance_cache[cache_key]
            params[loader['param']] = loader_instance

        return method(**params)
    
    def _execute_post_method(self, target, kls, kls_path, post_field, method):
        params = {}
        post_param = core.get_post_params(kls, post_field , self.metadata)
        if post_param['context']:
            params['context'] = self.context
        if post_param['ancestor_context']:
            params['ancestor_context'] = self._prepare_ancestor_context()
        if post_param['parent']:
            params['parent'] = self.parent_contextvars['parent'].get()

        alias_map = self.object_collect_alias_map_store.get(id(target), {})
        if alias_map:
            for collector in post_param['collectors']:
                alias, param = collector['alias'], collector['param']
                signature = (kls_path, post_field, param)
                params[param] = alias_map[alias][signature]
        
        return method(**params)

    def _execute_post_default_handler(self, target, kls, kls_path, method):
        params = {}
        post_default_param = core.get_post_default_handler_params(kls, self.metadata)

        if post_default_param['context']:
            params['context'] = self.context
        if post_default_param['ancestor_context']:
            params['ancestor_context'] = self._prepare_ancestor_context()
        if post_default_param['parent']:
            params['parent'] = self.parent_contextvars['parent'].get()

        alias_map = self.object_collect_alias_map_store.get(id(target), {})
        if alias_map:
            for collector in post_default_param['collectors']:
                alias, param = collector['alias'], collector['param']
                signature = (kls_path, const.POST_DEFAULT_HANDLER, param)
                params[param] = alias_map[alias][signature]

        return method(**params)

    async def _resolve_obj_field(self, target, kls, field, trim_field, method):
        if self.ensure_type:
            if not method.__annotations__:
                raise MissingAnnotationError(f'{field}: return annotation is required')

        val = self._execute_resolver_method(kls, field, method)
        while iscoroutine(val) or asyncio.isfuture(val):
            val = await val

        if not getattr(method, const.HAS_MAPPER_FUNCTION, False):  # defined in util.mapper
            val = util.try_parse_data_to_target_field_type(target, trim_field, val)

        # continue dive deeper
        val = await self._resolve(val, target)

        setattr(target, trim_field, val)

    async def _resolve(self, target: T, parent) -> T:
        if isinstance(target, (list, tuple)):
            # list should not play as parent, use original parent.
            await asyncio.gather(*[self._resolve(t, parent) for t in target])

        if core.is_acceptable_instance(target):
            kls = target.__class__
            kls_path = util.get_kls_full_path(kls)

            self._prepare_collectors(target, kls)
            self._add_expose_fields(target)
            self._add_parent(parent)

            tasks = []

            # traversal and fetching data by resolve methods
            resolve_list, attribute_list = core.iter_over_object_resolvers_and_acceptable_fields(target, kls, self.metadata)
            for field, resolve_trim_field, method in resolve_list:
                tasks.append(self._resolve_obj_field(target, kls, field, resolve_trim_field, method))
            for field, attr_object in attribute_list:
                tasks.append(self._resolve(attr_object, target))
            await asyncio.gather(*tasks)

            # reverse traversal and run post methods
            for post_field, post_trim_field in core.iter_over_object_post_methods(kls, self.metadata):
                post_method = getattr(target, post_field)
                result = self._execute_post_method(target, kls, kls_path, post_field, post_method)

                # TODO:  post method support async, should be gathered instead of for + await
                while iscoroutine(result) or asyncio.isfuture(result):
                    result = await result
                    
                result = util.try_parse_data_to_target_field_type(target, post_trim_field, result)
                setattr(target, post_trim_field, result)

            default_post_method = getattr(target, const.POST_DEFAULT_HANDLER, None)
            if default_post_method:
                self._execute_post_default_handler(target, kls, kls_path, default_post_method)

            # collect after all done
            self._add_values_into_collectors(target, kls)

        return target

    async def resolve(self, target: T) -> T:
        if isinstance(target, list) and target == []: return target

        root_class = core.get_class(target)
        metadata = core.scan_and_store_metadata(root_class)
        self.metadata = core.convert_metadata_key_as_kls(metadata)

        self.loader_instance_cache = core.validate_and_create_loader_instance(
            self.loader_params,
            self.global_loader_param,
            self.loader_instances,
            self.metadata)
        
        has_context = core.has_context(self.metadata)
        if has_context and self.context is None:
            raise AttributeError('context is missing')
            
        await self._resolve(target, None)
        return target