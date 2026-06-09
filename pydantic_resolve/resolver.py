import os
import asyncio
from dataclasses import dataclass
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
METADATA_CACHE: dict[int, dict[type, Any]] = {}
T = TypeVar("T")


@dataclass
class _Node:
    """A node in BFS traversal with explicit context (no contextvars)."""
    node: object
    kls: type
    kls_path: str
    parent: object
    ancestor_context: dict
    # For collectors: reference to ancestor collectors this node should add to.
    # Populated during Phase B-1 (top-down prepare).
    ancestor_collectors: dict = None  # {alias: {sign: Collector}}


@dataclass
class _ResolveJob:
    bn: _Node
    field_name: str
    trim_field: str
    method: Callable


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


class Resolver:
    # define class attribute using constant to avoid hardcoded name
    locals()[const.ER_DIAGRAM] = None
    locals()[const.ER_DIAGRAM_PRE_GENERATOR] = None

    def __init__(
            self,
            loader_params: dict[Any, dict[str, Any]] | None = None,
            global_loader_param: dict[str, Any] | None = None,
            loader_instances: dict[Any, Any] | None = None,
            ensure_type=False,
            context: dict[str, Any] | None = None,
            debug=False,
            enable_from_attribute_in_type_adapter=False,
            annotation: type[T] | None=None,
            split_loader_by_type=False,
            resolved_hooks: list[Callable] | None = None,
            ):

        self.debug = debug or os.getenv("PYDANTIC_RESOLVE_DEBUG", "false").lower() == "true"

        self.performance = profile_util.Profile()
        self.loader_instance_cache = {}

        # for dataloader which has class attributes, you can assign the value at here
        self.loader_params = loader_params or {}

        # keys in global_loader_params are mutually exclusive with key-value pairs in loader_params
        # eg: Resolver(global_loader_param={'key_a': 1}, loader_params={'key_a': 1}) will raise exception
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

        self.split_loader_by_type = split_loader_by_type

        self.resolved_hooks = resolved_hooks or []

    def _validate_loader_instance(self, loader_instances: dict[Any, Any]):
        for cls, loader in loader_instances.items():
            if not issubclass(cls, DataLoader):
                raise AttributeError(f'{cls.__name__} must be subclass of DataLoader')
            if not isinstance(loader, cls):
                raise AttributeError(f'{loader.__class__.__name__} is not instance of {cls.__name__}')
        return True

    def _get_loader_instance(self, path: str, type_key):
        entry = self.loader_instance_cache.get(path)
        if entry is None:
            raise AttributeError(
                f'Loader instance not found for "{path}". '
                'Check Resolver loader_params/global_loader_param or loader_instances.'
            )
        if not self.split_loader_by_type:
            return entry
        # Nested structure: {path: {type_tuple: DataLoader}}
        instance = entry.get(type_key)
        if instance is None:
            raise AttributeError(
                f'Loader instance not found for "{path}" with type_key {type_key}. '
                'Check Resolver loader_params/global_loader_param or loader_instances.'
            )
        return instance

    # ──────────────────────────────────────────────────────────
    # BFS traversal
    # ──────────────────────────────────────────────────────────

    def _build_ancestor_path(self, bn: _Node, node_to_bn: dict[int, _Node]) -> list[str]:
        """Build class name path from root to this node (for profile timing keys)."""
        path = []
        current = bn
        while current is not None:
            path.append(current.kls.__name__)
            current = node_to_bn.get(id(current.parent)) if current.parent else None
        path.reverse()
        return path

    def _make_nodes(self, items: list, parent: object, ancestor_context: dict) -> list[_Node]:
        """Create _Node wrappers for a list of items."""
        nodes = []
        cache = self._kls_path_cache
        for item in items:
            if analysis.is_acceptable_instance(item):
                kls = item.__class__
                nodes.append(_Node(
                    node=item,
                    kls=kls,
                    kls_path=cache.get(kls, class_util.get_kls_full_name(kls)),
                    parent=parent,
                    ancestor_context=ancestor_context,
                ))
        return nodes

    def _child_ancestor_context(self, bn: _Node) -> dict:
        """Build ancestor context snapshot for children of a node."""
        child_ctx = dict(bn.ancestor_context)
        expose_dict: dict | None = getattr(bn.node, const.EXPOSE_TO_DESCENDANT, None)
        if expose_dict:
            for fld, alias in expose_dict.items():
                try:
                    child_ctx[alias] = getattr(bn.node, fld)
                except AttributeError:
                    raise AttributeError(f'{fld} does not exist')
        return child_ctx

    def _collect_children(self, val: object, parent: object, ancestor_context: dict) -> list[_Node]:
        """Collect Pydantic model instances from a resolved value as next-level nodes."""
        children = []
        cache = self._kls_path_cache
        if val is None:
            return children
        if isinstance(val, (list, tuple)):
            for item in val:
                if analysis.is_acceptable_instance(item):
                    kls = item.__class__
                    children.append(_Node(
                        node=item, kls=kls,
                        kls_path=cache.get(kls, class_util.get_kls_full_name(kls)),
                        parent=parent, ancestor_context=ancestor_context,
                    ))
        elif analysis.is_acceptable_instance(val):
            kls = val.__class__
            children.append(_Node(
                node=val, kls=kls,
                kls_path=cache.get(kls, class_util.get_kls_full_name(kls)),
                parent=parent, ancestor_context=ancestor_context,
            ))
        return children

    async def _do_resolve(self, job: _ResolveJob, node_to_bn: dict[int, _Node]) -> tuple[_Node, object]:
        """Execute a single resolve job. Set value on node, return (bn, val) for deferred child collection."""
        bn, field_name, trim_field, method = job.bn, job.field_name, job.trim_field, job.method

        tid = None
        path = []
        if self.debug:
            path = self._build_ancestor_path(bn, node_to_bn)
            tid = self.performance.get_timer(path).start()

        try:
            if self.ensure_type and not method.__annotations__:
                raise MissingAnnotationError(f'{field_name}: return annotation is required')

            # Execute resolve method with explicit context
            val = self._execute_resolve_method(
                bn.kls, field_name, method, bn.parent, bn.ancestor_context)

            while iscoroutine(val) or asyncio.isfuture(val):
                val = await val

            # Type conversion
            if not getattr(method, const.HAS_MAPPER_FUNCTION, False):
                val = conversion_util.try_parse_data_to_target_field_type(
                    bn.node, trim_field, val, self.enable_from_attribute_in_type_adapter)

            # Resolved hooks
            for hook in self.resolved_hooks:
                hook(bn.node, trim_field, val)

            object.__setattr__(bn.node, trim_field, val)
            return bn, val
        finally:
            if self.debug and tid is not None:
                self.performance.get_timer(path).end(tid)

    def _execute_resolve_method(
            self, kls: type, field: str, method: Callable,
            parent: object, ancestor_context: dict):
        """Execute resolve method with explicit context."""
        params = {}
        resolve_param = analysis.get_resolve_method_param(kls, field, self.metadata)

        if resolve_param['context']:
            params['context'] = self.context
        if resolve_param['ancestor_context']:
            params['ancestor_context'] = MappingProxyType(ancestor_context)
        if resolve_param['parent']:
            params['parent'] = parent

        for loader in resolve_param['dataloaders']:
            loader_instance = self._get_loader_instance(loader['path'], loader['type_key'])
            params[loader['param']] = loader_instance

        return method(**params)

    def _execute_post_method(self, bn: _Node, post_field: str, method: Callable):
        """Execute post method with explicit context."""
        params = {}
        post_param = analysis.get_post_method_params(bn.kls, post_field, self.metadata)

        if post_param['context']:
            params['context'] = self.context
        if post_param['ancestor_context']:
            params['ancestor_context'] = MappingProxyType(bn.ancestor_context)
        if post_param['parent']:
            params['parent'] = bn.parent

        for loader in post_param['dataloaders']:
            loader_instance = self._get_loader_instance(loader['path'], loader['type_key'])
            params[loader['param']] = loader_instance

        alias_map = self.object_level_collect_alias_map_store.get(id(bn.node), {})
        if alias_map:
            for collector in post_param['collectors']:
                signature = analysis.get_collector_sign(bn.kls_path, collector)
                alias, param = collector['alias'], collector['param']
                params[param] = alias_map[alias][signature]

        return method(**params)

    def _execute_post_default_handler(self, bn: _Node, method: Callable):
        """Execute post_default_handler with explicit context."""
        params = {}
        post_default_param = analysis.get_post_default_handler_params(bn.kls, self.metadata)

        if post_default_param is None:
            return

        if post_default_param['context']:
            params['context'] = self.context
        if post_default_param['ancestor_context']:
            params['ancestor_context'] = MappingProxyType(bn.ancestor_context)
        if post_default_param['parent']:
            params['parent'] = bn.parent

        alias_map = self.object_level_collect_alias_map_store.get(id(bn.node), {})
        if alias_map:
            for collector in post_default_param['collectors']:
                alias, param = collector['alias'], collector['param']
                signature = (bn.kls_path, const.POST_DEFAULT_HANDLER, param)
                params[param] = alias_map[alias][signature]

        return method(**params)

    def _add_values_into_collectors(self, bn: _Node):
        """Add values into ancestor collectors via explicit reference."""
        if bn.ancestor_collectors is None:
            return
        kls_meta = self.metadata[bn.kls]
        for field, alias in kls_meta['collect_dict'].items():
            alias_list = alias if isinstance(alias, (tuple, list)) else (alias,)

            for alias in alias_list:
                collectors = bn.ancestor_collectors.get(alias)
                if collectors:
                    for _, instance in collectors.items():
                        if isinstance(field, tuple):
                            val = [getattr(bn.node, f) for f in field]
                        else:
                            val = getattr(bn.node, field)
                        instance.add(val)

    # ──────────────────────────────────────────────────────────
    # Phase A: resolve top-down
    # ──────────────────────────────────────────────────────────

    def _collect_level_jobs(self, current_level: list[_Node]):
        """Collect resolve jobs and object_fields from all nodes in a level."""
        resolve_jobs: list[_ResolveJob] = []
        bn_object_fields: list[tuple[_Node, list]] = []
        metadata = self.metadata

        for bn in current_level:
            kls_meta = metadata[bn.kls]

            node = bn.node
            for resolve_field in kls_meta['resolve']:
                attr = getattr(node, resolve_field)
                trim_field = kls_meta['resolve_params'][resolve_field]['trim_field']
                resolve_jobs.append(_ResolveJob(bn, resolve_field, trim_field, attr))

            if kls_meta['object_fields']:
                obj_fields = []
                for attr_name in kls_meta['object_fields']:
                    attr = getattr(node, attr_name)
                    obj_fields.append((attr_name, attr))
                bn_object_fields.append((bn, obj_fields))

        return resolve_jobs, bn_object_fields

    def _collect_next_level(self, resolve_results, bn_object_fields):
        """Collect child nodes from resolved values and object_fields."""
        next_level = []

        # Children from resolved values
        for bn, val in resolve_results:
            child_ctx = self._child_ancestor_context(bn)
            next_level.extend(self._collect_children(val, bn.node, child_ctx))

        # Children from object_fields
        for bn, object_fields in bn_object_fields:
            child_ctx = self._child_ancestor_context(bn)
            for _field_name, attr_object in object_fields:
                if attr_object is None:
                    continue
                next_level.extend(
                    self._collect_children(attr_object, bn.node, child_ctx))

        return next_level

    async def _phase_a_resolve(self, levels: list[list[_Node]], node_to_bn: dict[int, _Node]):
        """Phase A: resolve_* methods execute top-down, level by level.
        All resolves at the same level run concurrently via asyncio.gather,
        maximizing DataLoader batch sizes."""
        while True:
            current = levels[-1]
            resolve_jobs, bn_object_fields = self._collect_level_jobs(current)

            # Execute all resolves concurrently (empty gather is a no-op)
            results = await asyncio.gather(
                *[self._do_resolve(job, node_to_bn) for job in resolve_jobs]
            )

            # No jobs at all → done
            if not resolve_jobs and not bn_object_fields:
                break

            # Collect children from resolved values and object_fields
            next_level = self._collect_next_level(results, bn_object_fields)

            if not next_level:
                break
            levels.append(next_level)

            for bn in next_level:
                node_to_bn[id(bn.node)] = bn

    # ──────────────────────────────────────────────────────────
    # Phase B: post bottom-up
    # ──────────────────────────────────────────────────────────

    def _phase_b_prepare_collectors(self, levels: list[list[_Node]], node_to_bn: dict[int, _Node]):
        """Phase B-1: prepare collectors top-down (root→leaf).
        Clone collectors for each node and build ancestor_collectors references."""
        for depth in range(len(levels)):
            for bn in levels[depth]:
                alias_map = analysis.generate_alias_map_with_cloned_collector(bn.kls, self.metadata)
                if alias_map:
                    self.object_level_collect_alias_map_store[id(bn.node)] = alias_map

                # Build ancestor_collectors: merge parent's collectors with this node's own
                ancestor_cols = {}
                if bn.parent is not None:
                    parent_bn = node_to_bn.get(id(bn.parent))
                    if parent_bn and parent_bn.ancestor_collectors:
                        ancestor_cols = {k: dict(v) for k, v in parent_bn.ancestor_collectors.items()}

                if alias_map:
                    for alias_name, sign_kv in alias_map.items():
                        if alias_name not in ancestor_cols:
                            ancestor_cols[alias_name] = {}
                        ancestor_cols[alias_name].update(sign_kv)

                bn.ancestor_collectors = ancestor_cols

    async def _phase_b_execute_posts(self, levels: list[list[_Node]], node_to_bn: dict[int, _Node]):
        """Phase B-2: execute post methods bottom-up, level by level.
        Within each level: named post methods run concurrently first,
        then post_default_handler runs serially, then add values into collectors."""
        for depth in range(len(levels) - 1, -1, -1):
            post_tasks = []
            default_post_nodes = []
            add_nodes = []
            post_timers: list[tuple[list[str], object]] = []

            for bn in levels[depth]:
                add_nodes.append(bn)

                if self.debug:
                    path = self._build_ancestor_path(bn, node_to_bn)
                    tid = self.performance.get_timer(path).start()
                    post_timers.append((path, tid))

                kls_meta = self.metadata[bn.kls]
                for post_field in kls_meta['post']:
                    attr = getattr(bn.node, post_field)
                    trim_field = kls_meta['post_params'][post_field]['trim_field']
                    post_tasks.append(
                        self._execute_post_field(bn, post_field, trim_field, attr))

                default_post_method = getattr(bn.node, const.POST_DEFAULT_HANDLER, None)
                if default_post_method:
                    default_post_nodes.append((bn, default_post_method))

            await asyncio.gather(*post_tasks)

            for bn, method in default_post_nodes:
                val = self._execute_post_default_handler(bn, method)
                while iscoroutine(val) or asyncio.isfuture(val):
                    val = await val

            if self.debug:
                for path, tid in post_timers:
                    self.performance.get_timer(path).end(tid)

            for bn in add_nodes:
                self._add_values_into_collectors(bn)

    # ──────────────────────────────────────────────────────────
    # BFS traversal entry point
    # ──────────────────────────────────────────────────────────

    async def _traverse(self, root):
        """BFS level-by-level resolution. Two phases: resolve (top-down), post (bottom-up)."""
        if isinstance(root, (list, tuple)):
            items = list(root)
        else:
            items = [root]

        level_0 = self._make_nodes(items, parent=None, ancestor_context={})
        if not level_0:
            return root

        levels = [level_0]
        node_to_bn: dict[int, _Node] = {id(bn.node): bn for bn in level_0}

        await self._phase_a_resolve(levels, node_to_bn)
        self._phase_b_prepare_collectors(levels, node_to_bn)
        await self._phase_b_execute_posts(levels, node_to_bn)

        return root

    async def _execute_post_field(
            self, bn: _Node, post_field: str, post_trim_field: str, method: Callable):
        """Execute a single post method field."""
        val = self._execute_post_method(bn, post_field, method)

        while iscoroutine(val) or asyncio.isfuture(val):
            val = await val

        if not getattr(method, const.HAS_MAPPER_FUNCTION, False):
            val = conversion_util.try_parse_data_to_target_field_type(
                bn.node, post_trim_field, val, self.enable_from_attribute_in_type_adapter)

        object.__setattr__(bn.node, post_trim_field, val)

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
            self.context,
            split_loader_by_type=self.split_loader_by_type)

        has_context = analysis.has_context(self.metadata)
        if has_context and self.context is None:
            raise AttributeError('context is missing')

        # Build kls → kls_path cache from metadata
        self._kls_path_cache = {kls: meta['kls_path'] for kls, meta in self.metadata.items()}

        await self._traverse(node)

        if self.debug:
            self.performance.report()

        return node
