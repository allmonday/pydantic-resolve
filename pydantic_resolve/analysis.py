import copy
import inspect
from typing import TypedDict
from inspect import isfunction
from collections import defaultdict
from pydantic import BaseModel
import pydantic_resolve.constant as const
import pydantic_resolve.utils.class_util as class_util
from pydantic_resolve.utils.collector import ICollector, pre_generate_collector_config
from pydantic_resolve.utils.depend import Depends
from pydantic_resolve.utils.er_diagram import ErLoaderPreGenerator
from pydantic_resolve.exceptions import ResolverTargetAttrNotFound, MissingCollector
from pydantic_resolve.utils.expose import pre_generate_expose_config

class DataLoaderType(TypedDict):
    param: str
    kls: type
    path: str
    request_type: list[type]

class CollectorType(TypedDict):
    field: str 
    param: str
    instance: object
    alias: str
    
class ResolveMethodType(TypedDict):
    trim_field: str
    context: bool
    parent: bool
    ancestor_context: bool
    dataloaders: list[DataLoaderType]

class PostMethodType(TypedDict):
    trim_field: str
    context: bool
    parent: bool
    ancestor_context: bool
    dataloaders: list[DataLoaderType]
    collectors: list[CollectorType] 

class PostDefaultHandlerType(TypedDict):
    context: bool
    parent: bool
    ancestor_context: bool
    collectors: list[CollectorType]

class KlsMetaType(TypedDict):
    resolve: list[str]
    post: list[str]
    resolve_params: dict[str, ResolveMethodType]
    post_params: dict[str, PostMethodType]
    post_default_handler_params: PostDefaultHandlerType | None
    raw_object_fields: list[str] # store the original field names
    object_fields: list[str]
    expose_dict: dict
    collect_dict: dict
    kls: type
    has_context: bool
    should_traverse: bool

class LoaderQueryMetaRequestType(TypedDict):
    name: type
    fields: list[str]

class LoaderQueryMeta(TypedDict):
    required_types: list
    fields: list[str]

MetaType = dict[str, KlsMetaType]

class MappedMetaMemberType(KlsMetaType):
    kls_path: str
    alias_map_proto: dict[str, dict[tuple[str, str, str], object]]

MappedMetaType = dict[type, MappedMetaMemberType]


def _scan_resolve_method(method, field: str, request_types: list[type]) -> ResolveMethodType:
    result: ResolveMethodType = {
        'trim_field': field.replace(const.RESOLVE_PREFIX, ''),
        'context': False,
        'parent': False,
        'ancestor_context': False,
        'dataloaders': []  # collect func or class, do not create instance
    }
    signature = inspect.signature(method)

    if signature.parameters.get('context'):
        result['context'] = True

    if signature.parameters.get('ancestor_context'):
        result['ancestor_context'] = True

    if signature.parameters.get('parent'):
        result['parent'] = True

    for name, param in signature.parameters.items():
        if isinstance(param.default, Depends):
            info: DataLoaderType = { 
                'param': name,
                'kls': param.default.dependency,  # for later initialization
                'path': class_util.get_kls_full_name(param.default.dependency),
                'request_type': request_types
            }
            result['dataloaders'].append(info)

    for name, param in signature.parameters.items():
        if isinstance(param.default, ICollector):
            raise AttributeError("Collector is not available in resolve_method")

    return result


def _scan_post_method(method, field: str, request_types: list[type]) -> PostMethodType:
    result: PostMethodType = {
        'trim_field': field.replace(const.POST_PREFIX, ''),
        'context': False,
        'ancestor_context': False,
        'parent': False,
        'dataloaders': [],
        'collectors': []
    }
    signature = inspect.signature(method)

    if signature.parameters.get('context'):
        result['context'] = True

    if signature.parameters.get('ancestor_context'):
        result['ancestor_context'] = True

    if signature.parameters.get('parent'):
        result['parent'] = True

    
    for name, param in signature.parameters.items():
        if isinstance(param.default, Depends):
            loader_info: DataLoaderType = { 
                'param': name,
                'kls': param.default.dependency,  # for later initialization
                'path': class_util.get_kls_full_name(param.default.dependency),
                'request_type': request_types
            }
            result['dataloaders'].append(loader_info)

        if isinstance(param.default, ICollector):
            info: CollectorType = {
                'field': field,
                'param': name,
                'instance': param.default,
                'alias': param.default.alias 
            }
            result['collectors'].append(info)

            
    return result


def _scan_post_default_handler(method) -> PostDefaultHandlerType:
    result: PostDefaultHandlerType = {
        'context': False,
        'ancestor_context': False,
        'parent': False,
        'collectors': []
    }
    signature = inspect.signature(method)

    if signature.parameters.get('context'):
        result['context'] = True

    if signature.parameters.get('ancestor_context'):
        result['ancestor_context'] = True

    if signature.parameters.get('parent'):
        result['parent'] = True

    for name, param in signature.parameters.items():
        if isinstance(param.default, ICollector):
            info: CollectorType = {
                'field': const.POST_DEFAULT_HANDLER,
                'param': name,
                'instance': param.default,
                'alias': param.default.alias 
            }
            result['collectors'].append(info)

    return result


class Analytic:
    """
    Analyze pydantic models to extract metadata for resolution.
    
    This class traverses the pydantic model tree to collect:
    - resolve methods
    - post methods
    - expose configurations
    - collector configurations
    - object fields that need traversal
    """
    def __init__(self, er_pre_generator: ErLoaderPreGenerator | None=None) -> None:
        self.expose_set = set()
        self.collect_set = set()
        self.metadata: MetaType = {}
        self.er_pre_generator = er_pre_generator

    def _get_request_type_for_loader(self, object_field_pairs, field_name: str):
        return object_field_pairs.get(field_name)

    def _get_all_fields_and_object_fields(self, kls: type):
        if class_util.safe_issubclass(kls, BaseModel):
            all_fields = set(class_util.get_pydantic_field_keys(kls))
            object_fields = list(class_util.get_pydantic_fields(kls))  # dive and recursively analysis
        else:
            raise TypeError('invalid type: should be pydantic object')  # noqa
        return all_fields, object_fields, {k: v for k, v in object_fields}

    def _has_post_default_handler(self, kls: type) -> bool:
        fields = dir(kls)
        fields = [f for f in fields if f == const.POST_DEFAULT_HANDLER and isfunction(getattr(kls, f))]
        return len(fields) > 0

    def _get_resolve_and_post_fields(self, kls: type):
        fields = dir(kls)

        resolve_fields = [f for f in fields if f.startswith(const.RESOLVE_PREFIX) and isfunction(getattr(kls, f))]
        post_fields = [
            f for f in fields if f.startswith(const.POST_PREFIX)
            and f != const.POST_DEFAULT_HANDLER
            and isfunction(getattr(kls, f))
        ]
        fields_with_resolver = {field.replace(const.RESOLVE_PREFIX, '') for field in resolve_fields}
        return resolve_fields, post_fields, fields_with_resolver

    def _validate_resolve_and_post_fields(self, resolve_fields, post_fields, all_fields):
        for field in resolve_fields:
            resolve_field = field.replace(const.RESOLVE_PREFIX, '')
            if resolve_field not in all_fields:
                raise ResolverTargetAttrNotFound(f"attribute {resolve_field} not found")

        for field in post_fields:
            post_field = field.replace(const.POST_PREFIX, '')
            if post_field not in all_fields:
                raise ResolverTargetAttrNotFound(f"attribute {post_field} not found")

    def _validate_expose(self, expose_dict: dict, kls_name: str):
        if not isinstance(expose_dict, dict):
            raise TypeError(f'{const.EXPOSE_TO_DESCENDANT} is not dict')
        for _, v in expose_dict.items():
            if v in self.expose_set:
                raise ValueError(f'Expose alias name conflicts, please check: {kls_name}')
            self.expose_set.add(v)

    def _add_collector_info(self, post_params):
        """
        add collector alias during _walker (breadth first traversal)
        so that it should ensure the definition of collector is always before usage
        which means collector should always be defined before ancestor nodes actually send data.
        """
        for _, param in post_params.items():
            for collector in param['collectors']:
                self.collect_set.add(collector['alias'])

    def _add_collector_info_for_default_handler(self, post_default_params):
        """
        same like _add_collector_info
        """
        if post_default_params is not None:
            for collector in post_default_params['collectors']:
                self.collect_set.add(collector['alias'])

    def _validate_collector(self, collect_dict: dict, kls_name: str):
        """
        validate if the collector is declared in ancestor nodes.

        available format of `__pydantic_resolve_collect__`

        class A(BaseModel):
            __pydantic_resolve_collect__ = {
                'name': 'collector_a',                                  # send name to collector_a
                ('name', 'age'): 'collector_b',                         # send ('name', 'age') to collector_b
                'name': ('collector_c', 'collector_d'),                 # send name to both collector_c and d
                ('name', 'age'): ('collector_e', 'collector_f'),        # send ('name', 'age') to both collector_e and f
            }
        """
        if type(collect_dict) is not dict:
            raise AttributeError(f'{const.COLLECTOR_CONFIGURATION} is not dict')

        for _, collector in collect_dict.items():
            collectors = collector if isinstance(collector, (list, tuple)) else (collector,)
            for c in collectors:
                if c not in self.collect_set:
                    raise MissingCollector(f'Collector alias name not found in ancestor, please check: {kls_name}')

    def _has_config(self, info: KlsMetaType):
        result = (
            len(info['resolve']) > 0 or
            len(info['post']) > 0 or
            len(info['collect_dict']) > 0 or
            len(info['expose_dict']) > 0 or
            info['post_default_handler_params'] is not None
        )
        return result

    def _populate_ancestors(self, parents: list) -> None:
        """
        mark should traverse to plan a minimal traversal path
        """
        for field, kls_name in parents:
            # normally, array size is small
            if field in self.metadata[kls_name]['raw_object_fields'] and \
                    field not in self.metadata[kls_name]['object_fields']:
                self.metadata[kls_name]['object_fields'].append(field)
            self.metadata[kls_name]['should_traverse'] = True

    def _walker(self, kls: type, ancestors: list[tuple[str, str]]) -> None:
        kls_name = class_util.get_kls_full_name(kls)
        cached_metadata = self.metadata.get(kls_name)
        if cached_metadata:
            # if populated by previous node, or self has_config
            if cached_metadata['should_traverse'] or self._has_config(cached_metadata):
                self._populate_ancestors(ancestors)
            return

        # based on ER diagram, generate resolve + dataloader by field's metadata settings
        if self.er_pre_generator: 
            self.er_pre_generator.prepare(kls)
        
        # generate expose and collector config based on field's metadata settings
        # __pydantic_resolve_expose__ and __pydantic_resolve_collect__
        pre_generate_expose_config(kls)
        pre_generate_collector_config(kls)

        # prepare fields, with resolve_, post_ reserved
        all_fields, object_fields, object_field_pairs = self._get_all_fields_and_object_fields(kls)
        resolve_fields, post_fields, fields_with_resolver = self._get_resolve_and_post_fields(kls)
        self._validate_resolve_and_post_fields(resolve_fields, post_fields, all_fields)
        object_fields_without_resolver = [a[0] for a in object_fields if a[0] not in fields_with_resolver]

        # - scan expose and collect (__pydantic_resolve_xxx__)
        expose_dict = getattr(kls, const.EXPOSE_TO_DESCENDANT, {})
        collect_dict = getattr(kls, const.COLLECTOR_CONFIGURATION, {})
        self._validate_expose(expose_dict, kls_name)

        resolve_params = {
            field: _scan_resolve_method(
                getattr(kls, field),
                field,
                self._get_request_type_for_loader(
                    object_field_pairs,
                    field.replace(const.RESOLVE_PREFIX, '')))
            for field in resolve_fields
        }
        post_params = {
            field: _scan_post_method(
                getattr(kls, field),
                field,
                self._get_request_type_for_loader(
                    object_field_pairs,
                    field.replace(const.POST_PREFIX, '')))
            for field in post_fields
        }
        post_default_handler_params = _scan_post_default_handler(getattr(kls, const.POST_DEFAULT_HANDLER)) if self._has_post_default_handler(kls) else None

        # check context config
        resolve_context = any([p['context'] for p in resolve_params.values()])
        post_context = any([p['context'] for p in post_params.values()])
        post_default_context = post_default_handler_params['context'] if post_default_handler_params else False
        has_context = resolve_context or post_context or post_default_context

        # check collector
        self._add_collector_info(post_params)
        self._add_collector_info_for_default_handler(post_default_handler_params)
        self._validate_collector(collect_dict, kls_name)

        info: KlsMetaType = {
            'resolve': resolve_fields,
            'resolve_params': resolve_params,
            'post': post_fields,
            'post_params': post_params,
            'post_default_handler_params': post_default_handler_params,
            'raw_object_fields': object_fields_without_resolver,
            'object_fields': [],
            'expose_dict': expose_dict,
            'collect_dict': collect_dict,
            'kls': kls,
            'has_context': has_context,
            'should_traverse': False
        }
        self.metadata[kls_name] = info

        # visit fields (pydantic class) without resolve method
        for field, shelled_types in (obj for obj in object_fields if obj[0] in object_fields_without_resolver):
            for shelled_type in shelled_types:
                self._walker(shelled_type, ancestors + [(field, kls_name)])

        # visit fields with resolve method
        for field, shelled_types in (obj for obj in object_fields if obj[0] in fields_with_resolver):
            for shelled_type in shelled_types:
                self._walker(shelled_type, ancestors + [(field, kls_name)])

        should_traverse = info['should_traverse'] or self._has_config(info)

        if should_traverse:
            self._populate_ancestors(ancestors)

        info['should_traverse'] = should_traverse

    def scan(self, root_class: type) -> MetaType:
        """Public method to perform metadata scan and return the metadata map."""
        # reset state for each scan
        self.expose_set = set()
        self.collect_set = set()
        self.metadata = {}

        core_types = class_util.get_core_types(root_class)

        for ct in core_types:
            class_util.update_forward_refs(ct)

        for ct in core_types:
            self._walker(ct, [])

        return self.metadata


def convert_metadata_key_as_kls(metadata: MetaType) -> MappedMetaType:  # type: ignore[valid-type]
    """ use kls as map key for performance """
    kls_metadata = {}
    for k, v in metadata.items():
        _kls_meta: MappedMetaMemberType = {
            **v, 
            'kls_path':k,
            'alias_map_proto': {}
        }
        alias_map = _calc_alias_map_from_collectors(_kls_meta)
        _kls_meta['alias_map_proto'] = alias_map
        kls_metadata[v['kls']] = _kls_meta
    
    return kls_metadata


def _calc_alias_map_from_collectors(kls_meta: MappedMetaMemberType) -> dict:
    post_params = kls_meta['post_params']
    kls_path = kls_meta['kls_path']

    alias_map = defaultdict(dict)

    def add_collector(collector: CollectorType) -> None:
        """
        class A(BaseModel):
            def post_name(collector=Collector('name')):
                ...
        kls_path: module_name.A
        field: post_name
        param: collector_a

        sign = ('module_name.A', 'post_name', 'collector_a')

        return { 'name': { sign: collector_instance } }
        """
        sign = get_collector_sign(kls_path, collector)
        alias_map[collector['alias']][sign] = collector['instance']

    for _, param in post_params.items():
        for collector in param['collectors']:
            add_collector(collector)

    # post_default_handler
    post_default_handler_params = kls_meta['post_default_handler_params']
    if post_default_handler_params:
        for collector in post_default_handler_params['collectors']:
            add_collector(collector)

    return alias_map


def is_acceptable_kls(kls: type) -> bool:
    return class_util.safe_issubclass(kls, BaseModel)


def is_acceptable_instance(target: object):
    return isinstance(target, BaseModel)


def get_resolve_fields_and_object_fields_from_object(node: object, kls: type, mapped_metadata: MappedMetaType):
    """
    resolve_fields: a field with resolve_field method
    object_fields: a field without resolve_field method but is an object (should traversal)
    """
    resolve_fields, object_fields = [], []
    kls_meta = mapped_metadata.get(kls)

    if kls_meta is None:
        return [], []

    for resolve_field in kls_meta['resolve']:
        attr = getattr(node, resolve_field)
        trim_field = kls_meta['resolve_params'][resolve_field]['trim_field']
        resolve_fields.append((resolve_field, trim_field, attr))

    for attr_name in kls_meta['object_fields']:
        attr = getattr(node, attr_name)
        object_fields.append((attr_name, attr))

    return resolve_fields, object_fields


def get_post_methods(node: object, kls: type, mapped_metadata: MappedMetaType):
    kls_meta = mapped_metadata.get(kls)

    if kls_meta is None:
        return []

    for post_field in kls_meta['post']:
        attr = getattr(node, post_field)
        trim_field = kls_meta['post_params'][post_field]['trim_field']
        yield post_field, trim_field, attr


def get_resolve_method_param(kls: type, resolve_field: str, mapped_metadata: MappedMetaType):
    kls_meta = mapped_metadata.get(kls, {})
    return kls_meta['resolve_params'][resolve_field]


def get_post_method_params(kls: type, post_field: str, mapped_metadata: MappedMetaType):
    kls_meta = mapped_metadata.get(kls, {})
    return kls_meta['post_params'][post_field]


def get_post_default_handler_params(kls: type, mapped_metadata: MappedMetaType):
    kls_meta = mapped_metadata.get(kls, {})
    return kls_meta['post_default_handler_params']


def get_collector_sign(kls_path: str, collector: CollectorType) -> tuple:
    return (kls_path, collector['field'], collector['param'])


def generate_alias_map_with_cloned_collector(kls: type, mapped_metadata: MappedMetaType):
    kls_meta = mapped_metadata.get(kls, {})
    return { alias: {
        sign: copy.deepcopy(collector) for sign, collector in v.items()
    } for alias, v in kls_meta['alias_map_proto'].items()}


def get_collector_candidates(kls: type, metadata: MappedMetaType):
    kls_meta = metadata.get(kls, {})
    collect_dict = kls_meta['collect_dict']

    for field, alias in collect_dict.items():
        yield field, alias


def has_context(mapped_metadata: MappedMetaType):
    return any([ m['has_context'] for m in mapped_metadata.values()])