import os
import asyncio
import warnings
import contextvars
from inspect import iscoroutine
from typing import TypeVar, Callable, Any
from aiodataloader import DataLoader
from types import MappingProxyType

from pydantic_resolve import analysis
from pydantic_resolve.exceptions import MissingAnnotationError
import pydantic_resolve.loader_manager
import pydantic_resolve.utils.conversion as conversion_util
import pydantic_resolve.utils.class_util as class_util
import pydantic_resolve.constant as const
import pydantic_resolve.utils.profile as profile_util

# Two-level cache: id(resolver_class) -> {root_class -> metadata}
# This isolates caches for different resolver classes (created via config_resolver)
# since different resolver classes may have different er_pre_generator configurations
METADATA_CACHE: dict[int, dict[type, any]] = {}
T = TypeVar("T")


def _get_metadata_from_cache(resolver_class_id: int, root_class: type):
    """Get metadata from two-level cache."""
    resolver_cache = METADATA_CACHE.get(resolver_class_id)
    if resolver_cache is None:
        return None
    return resolver_cache.get(root_class)


def _set_metadata_to_cache(resolver_class_id: int, root_class: type, metadata) -> None:
    """Set metadata to two-level cache."""
    if resolver_class_id not in METADATA_CACHE:
        METADATA_CACHE[resolver_class_id] = {}
    METADATA_CACHE[resolver_class_id][root_class] = metadata


def _safe_reset_contextvar(contextvar: contextvars.ContextVar, token):
    """Safely reset a contextvar, ignoring errors if token is from a different context."""
    try:
        contextvar.reset(token)
    except (ValueError, LookupError):
        # Token was created in a different context or already reset
        pass


class Resolver:
    # define class attribute using constant to avoid hardcoded name
    locals()[const.ER_DIAGRAM] = None
    locals()[const.ER_DIAGRAM_PRE_GENERATOR] = None

    def __init__(
            self,
            loader_filters: dict[Any, dict[str, Any]] | None = None,  # deprecated
            loader_params: dict[Any, dict[str, Any]] | None = None,
            global_loader_filter: dict[str, Any] | None = None,  # deprecated
            global_loader_param: dict[str, Any] | None = None,
            loader_instances: dict[Any, Any] | None = None,
            ensure_type=False,
            context: dict[str, Any] | None = None,
            debug=False,
            enable_from_attribute_in_type_adapter=False,
            annotation: type[T] | None=None
            ):
        
        self.debug = debug or os.getenv("PYDANTIC_RESOLVE_DEBUG", "false").lower() == "true"

        self.performance = profile_util.Profile()
        self.loader_instance_cache = {}

        # Optimization: Use single dict-based ContextVar for all ancestors
        # Instead of multiple ContextVars (one per field), use one that holds a dict
        self._ancestor_contextvar = contextvars.ContextVar(
            '_ancestors',
            default=MappingProxyType({}),
        )

        # Optimization: Use single dict-based ContextVar for collectors
        self._collector_contextvar = contextvars.ContextVar(
            '_collectors',
            default=MappingProxyType({}),
        )

        # Optimization: Use single dict-based ContextVar for collectors
        self._collector_contextvar = contextvars.ContextVar(
            '_collectors',
            default=MappingProxyType({})
        )

        # Pre-create parent ContextVar
        self._parent_contextvar = contextvars.ContextVar('parent', default=None)

        # Legacy compatibility - keep dict-based access for now
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

        # only use with pydantic v2
        # for scenario of upgrading from pydantic v1
        # in v1, it supports parsing from another pydantic object which contains not only the fields target
        # class required but also other fields, but in v2, this will raise exception, type adapter by default only support parsing from 
        # dict or pydantic object which is exactly the same with target class
        #
        # class A(BaseModel):
        #   name: str
        #   id: int
        # 
        # class B(BaseModel):
        #   name: str
        # 
        # in pydantc v1, parse_obj_as can parse B from A, but in v2, it will raise exception
        # however, with typeAdapter.validate_python(data, from_attribute=True), it can work
        # the cost is performance (about 10% overhead), so it is disabled by default
        self.enable_from_attribute_in_type_adapter = enable_from_attribute_in_type_adapter \
            or os.getenv("PYDANTIC_RESOLVE_ENABLE_FROM_ATTRIBUTE", "false").lower() == "true"

        self.ensure_type = ensure_type
        self.context = MappingProxyType(context) if context else None
        self.metadata = {}
        self.object_level_collect_alias_map_store: dict[int, dict] = {}

        # if user provide annotation, it will skip the deduction from input value
        self.annotation = annotation

    def _validate_loader_instance(self, loader_instances: dict[Any, Any]):
        for cls, loader in loader_instances.items():
            if not issubclass(cls, DataLoader):
                raise AttributeError(f'{cls.__name__} must be subclass of DataLoader')
            if not isinstance(loader, cls):
                raise AttributeError(f'{loader.__name__} is not instance of {cls.__name__}')
        return True

    def _get_loader_instance(self, cache_key: str):
        try:
            return self.loader_instance_cache[cache_key]
        except KeyError as exc:
            raise AttributeError(
                f'Loader instance not found for "{cache_key}". '
                'Check Resolver loader_params/global_loader_param or loader_instances.'
            ) from exc
    
    def _prepare_collectors(self, node: object, kls: type):
        alias_map = analysis.generate_alias_map_with_cloned_collector(kls, self.metadata)
        if alias_map:
            # store for later post methods
            self.object_level_collect_alias_map_store[id(node)] = alias_map

            # Optimization: Use single dict-based ContextVar
            current_collectors = self._collector_contextvar.get()
            new_collectors = dict(current_collectors)

            for alias_name, sign_collector_kv in alias_map.items():
                if alias_name not in new_collectors:
                    new_collectors[alias_name] = {}

                current_pair = new_collectors[alias_name]
                if set(sign_collector_kv.keys()) - set(current_pair.keys()):
                    new_collectors[alias_name] = {**current_pair, **sign_collector_kv}

            token = self._collector_contextvar.set(new_collectors)
            return lambda: _safe_reset_contextvar(self._collector_contextvar, token)

        return lambda: None

    def _prepare_parent(self, node: object):
        # Optimization: Use pre-created ContextVar
        token = self._parent_contextvar.set(node)
        return lambda: _safe_reset_contextvar(self._parent_contextvar, token)

    def _prepare_expose_fields(self, node: object):
        expose_dict: dict | None = getattr(node, const.EXPOSE_TO_DESCENDANT, None)
        if expose_dict:
            # Optimization: Use single dict-based ContextVar
            current_ancestors = self._ancestor_contextvar.get()
            new_ancestors = dict(current_ancestors)

            for field, alias in expose_dict.items():
                try:
                    val = getattr(node, field)
                except AttributeError:
                    raise AttributeError(f'{field} does not exist')
                new_ancestors[alias] = val

            token = self._ancestor_contextvar.set(new_ancestors)
            return lambda: _safe_reset_contextvar(self._ancestor_contextvar, token)

        return lambda: None

    def _prepare_ancestor_context(self):
        # Optimization: Single .get() call instead of multiple
        return self._ancestor_contextvar.get()

    def _execute_resolve_method(
            self,
            kls: type,
            field: str,
            method: Callable):

        params = {}
        resolve_param = analysis.get_resolve_method_param(kls, field, self.metadata)

        if resolve_param['context']:
            params['context'] = self.context
        if resolve_param['ancestor_context']:
            params['ancestor_context'] = self._prepare_ancestor_context()
        if resolve_param['parent']:
            params['parent'] = self._parent_contextvar.get()
        
        for loader in resolve_param['dataloaders']:
            cache_key = loader['path']
            loader_instance = self._get_loader_instance(cache_key)
            params[loader['param']] = loader_instance

        return method(**params)
    
    def _execute_post_method(
            self,
            node: object,
            kls: type,
            kls_path: str,
            field: str,
            method: Callable):

        params = {}
        post_param = analysis.get_post_method_params(kls, field, self.metadata)

        if post_param['context']:
            params['context'] = self.context
        if post_param['ancestor_context']:
            params['ancestor_context'] = self._prepare_ancestor_context()
        if post_param['parent']:
            params['parent'] = self._parent_contextvar.get()
        
        for loader in post_param['dataloaders']:
            cache_key = loader['path']
            loader_instance = self._get_loader_instance(cache_key)
            params[loader['param']] = loader_instance

        alias_map = self.object_level_collect_alias_map_store.get(id(node), {})
        if alias_map:
            for collector in post_param['collectors']:
                signature = analysis.get_collector_sign(kls_path, collector)
                alias, param = collector['alias'], collector['param']
                params[param] = alias_map[alias][signature]
        
        return method(**params)

    def _execute_post_default_handler(
            self,
            node: object,
            kls: type,
            kls_path: str,
            method: Callable):

        params = {}
        post_default_param = analysis.get_post_default_handler_params(kls, self.metadata)

        if post_default_param is None:
            return

        if post_default_param['context']:
            params['context'] = self.context
        if post_default_param['ancestor_context']:
            params['ancestor_context'] = self._prepare_ancestor_context()
        if post_default_param['parent']:
            params['parent'] = self._parent_contextvar.get()

        alias_map = self.object_level_collect_alias_map_store.get(id(node), {})
        if alias_map:
            for collector in post_default_param['collectors']:
                alias, param = collector['alias'], collector['param']
                signature = (kls_path, const.POST_DEFAULT_HANDLER, param)
                params[param] = alias_map[alias][signature]

        return method(**params)

    def _add_values_into_collectors(self, node: object, kls: type):
        for field, alias in analysis.get_collector_candidates(kls, self.metadata):
            alias_list = alias if isinstance(alias, (tuple, list)) else (alias,)

            for alias in alias_list:
                # Use the single dict-based ContextVar
                collectors = self._collector_contextvar.get()
                if alias in collectors:
                    for _, instance in collectors[alias].items():
                        if isinstance(field, tuple):  # only tuple are allowed to be key
                            val = [getattr(node, f) for f in field]
                        else:
                            val = getattr(node, field)
                        instance.add(val)

    async def _execute_resolve_method_field(
            self,
            node: object,
            kls: type,
            field: str,
            trim_field: str,
            method: Callable):
        if self.ensure_type:
            if not method.__annotations__:
                raise MissingAnnotationError(f'{field}: return annotation is required')

        val = self._execute_resolve_method(kls, field, method)

        while iscoroutine(val) or asyncio.isfuture(val):
            val = await val

        if not getattr(method, const.HAS_MAPPER_FUNCTION, False):  # defined in util.mapper
            val = conversion_util.try_parse_data_to_target_field_type(
                node,
                trim_field,
                val,
                self.enable_from_attribute_in_type_adapter)

        val = await self._traverse(val, node)
        setattr(node, trim_field, val)

    async def _execute_post_method_field(
         self,
         node: object,
         kls: type,
         kls_path: str,
         field: str,
         trim_field: str,
         method: Callable
    ):
        val = self._execute_post_method(node, kls, kls_path, field, method)

        while iscoroutine(val) or asyncio.isfuture(val):
            val = await val
            
        if not getattr(method, const.HAS_MAPPER_FUNCTION, False):  # defined in util.mapper
            val = conversion_util.try_parse_data_to_target_field_type(
                node,
                trim_field,
                val,
                self.enable_from_attribute_in_type_adapter)

        setattr(node, trim_field, val)
    
    async def _traverse(self, node: T, parent: object) -> T:
        """
        life cycle:
        - prepare 
            - collectors, 
            - ancestor expose fields 
            - parent
        - execute 
            - resolve method fields/ object fields
            - post method fields
            - post default handler
        - collect
            - values into ancestor collectors
        - return node
        """
        if isinstance(node, (list, tuple)):
            await asyncio.gather(*[self._traverse(t, parent) for t in node])
            return node

        if not analysis.is_acceptable_instance(node):
            return node

        kls = node.__class__
        kls_path = class_util.get_kls_full_name(kls)

        reset1 = self._prepare_collectors(node, kls)
        reset2 = self._prepare_expose_fields(node)
        reset3 = self._prepare_parent(parent)

        token = None
        tid = None
        new_ancestors = None

        if self.debug:
            ancestors = self.ancestor_list.get()
            new_ancestors = ancestors + [node.__class__.__name__]
            token = self.ancestor_list.set(new_ancestors)
            tid = self.performance.get_timer(new_ancestors).start()

        try:
            resolve_tasks = []
            post_tasks = []

            # resolve process
            resolve_fields, object_fields = analysis.get_resolve_fields_and_object_fields_from_object(node, kls, self.metadata)
            for field, resolve_trim_field, method in resolve_fields:
                resolve_tasks.append(self._execute_resolve_method_field(
                    node=node, 
                    kls=kls, 
                    field=field, 
                    trim_field=resolve_trim_field, 
                    method=method))

            for field, attr_object in object_fields:
                resolve_tasks.append(self._traverse(attr_object, node))

            await asyncio.gather(*resolve_tasks)

            # post process
            for post_field, post_trim_field, method in analysis.get_post_methods(node, kls, self.metadata):
                post_tasks.append(self._execute_post_method_field(
                    node=node, 
                    kls=kls, 
                    kls_path=kls_path, 
                    field=post_field, 
                    trim_field=post_trim_field,
                    method=method))

            await asyncio.gather(*post_tasks)

            default_post_method = getattr(node, const.POST_DEFAULT_HANDLER, None)
            if default_post_method:
                val = self._execute_post_default_handler(node, kls, kls_path, default_post_method)
                while iscoroutine(val) or asyncio.isfuture(val):
                    val = await val

            self._add_values_into_collectors(node, kls)
        finally:
            if self.debug and tid is not None and new_ancestors is not None:
                self.performance.get_timer(new_ancestors).end(tid)  # type: ignore
            # reset all contextvars
            reset1()
            reset2()
            reset3()
            if self.debug and token is not None:
                _safe_reset_contextvar(self.ancestor_list, token)

        return node

    async def resolve(self, node: T) -> T:
        if isinstance(node, list) and node == []:
            return node

        # by default pydantic-resolve will deduce the root class from input node
        # but in some scenario like Union types, it is unable to deduce the root class
        # so user can provide the root class by annotation parameter
        root_class = self.annotation if self.annotation else class_util.get_class_of_object(node)
        resolver_class_id = id(self.__class__)

        # Check cache with resolver_class_id for isolation between different resolver configurations
        cached_metadata = _get_metadata_from_cache(resolver_class_id, root_class)
        if cached_metadata:
            self.metadata = cached_metadata
        else:
            metadata = analysis.convert_metadata_key_as_kls(
                analysis.Analytic(
                    er_pre_generator=getattr(self, const.ER_DIAGRAM_PRE_GENERATOR)
                ).scan(root_class)
            )
            _set_metadata_to_cache(resolver_class_id, root_class, metadata)
            self.metadata = metadata

        self.loader_instance_cache = pydantic_resolve.loader_manager.validate_and_create_loader_instance(
            self.loader_params,
            self.global_loader_param,
            self.loader_instances,
            self.metadata,
            self.context)
        
        has_context = analysis.has_context(self.metadata)
        if has_context and self.context is None:
            raise AttributeError('context is missing')

        self.ancestor_list = contextvars.ContextVar('ancestor_list', default=[])
            
        await self._traverse(node, None)

        if self.debug:
            self.performance.report()

        return node