import copy
import inspect
from typing import List, Type, Dict, Optional, Tuple
from inspect import isfunction, isclass
from collections import defaultdict
from aiodataloader import DataLoader
from pydantic import BaseModel
from dataclasses import is_dataclass, fields as dc_fields

import pydantic_resolve.constant as const
import pydantic_resolve.utils.class_util as class_util
from pydantic_resolve.utils.collector import ICollector
from pydantic_resolve.utils.depend import Depends
import pydantic_resolve.utils.params as params_util
from pydantic_resolve.exceptions import ResolverTargetAttrNotFound, LoaderFieldNotProvidedError, MissingCollector
import sys

if sys.version_info >= (3, 8):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict

class DataLoaderType(TypedDict):
    param: str
    kls: Type
    path: str
    request_type: List[Type]

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
    dataloaders: List[DataLoaderType]

class PostMethodType(TypedDict):
    trim_field: str
    context: bool
    parent: bool
    ancestor_context: bool
    dataloaders: List[DataLoaderType]
    collectors: List[CollectorType] 

class PostDefaultHandlerType(TypedDict):
    context: bool
    parent: bool
    ancestor_context: bool
    collectors: List[CollectorType]

class KlsMetaType(TypedDict):
    resolve: List[str]
    post: List[str]
    resolve_params: Dict[str, ResolveMethodType]
    post_params: Dict[str, PostMethodType]
    post_default_handler_params: Optional[PostDefaultHandlerType]
    raw_object_fields: List[str] # store the original field names
    object_fields: List[str]
    expose_dict: dict
    collect_dict: dict
    kls: Type
    has_context: bool
    should_traverse: bool

class LoaderQueryMetaRequestType(TypedDict):
    name: Type
    fields: List[str]

class LoaderQueryMeta(TypedDict):
    required_types: List
    fields: List[str]

MetaType = Dict[str, KlsMetaType]

class MappedMetaMemberType(KlsMetaType):
    kls_path: str
    alias_map_proto: Dict[str, Dict[Tuple[str, str, str], object]]

MappedMetaType = Dict[Type, MappedMetaMemberType]


def _scan_resolve_method(method, field: str, request_types: List[Type]) -> ResolveMethodType:
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


def _scan_post_method(method, field: str, request_types: List[Type]) -> PostMethodType:
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


def validate_and_create_loader_instance(
        loader_params,
        global_loader_param,
        loader_instances,
        metadata: MappedMetaType):
    """
    return loader_instance_cache

    validate: whether loader params are missing
    create: 
        - func
        - loader class
            - no param
            - has param
    """
    # fetch all loaders
    def _get_all_loaders_from_meta(metadata):
        for _, kls_info in metadata.items():
            for _, resolve_info in kls_info['resolve_params'].items():
                for loader in resolve_info['dataloaders']:
                    yield loader

            for _, post_info in kls_info['post_params'].items():
                for loader in post_info['dataloaders']:
                    yield loader
    
    def _create_instance(loader):
        """
        1. is class?
            - validate params
        2. is func """
        loader_kls, path = loader['kls'], loader['path']
        if isclass(loader_kls):
            loader = loader_kls()
            param_config = params_util.merge_dicts(
                global_loader_param,
                loader_params.get(loader_kls, {}))

            for field, has_default in class_util.get_fields_default_value_not_provided(loader_kls):
                try:
                    if has_default and field not in param_config:
                        continue

                    value = param_config[field]
                    setattr(loader, field, value)
                except KeyError:
                    raise LoaderFieldNotProvidedError(f'{path}.{field} not found in Resolver()')
            return loader
        else:
            loader = DataLoader(batch_load_fn=loader_kls)  # type:ignore
            return loader
    
    def _get_all_fields(kls):
        if class_util.safe_issubclass(kls, BaseModel):
            return list(class_util.get_pydantic_field_keys(kls))

        elif is_dataclass(kls):
            return [f.name for f in dc_fields(kls)]

        else:
            raise AttributeError('invalid type: should be pydantic object or dataclass object')  #noqa

    def _generate_meta(types: List[List[Type]]):
        _fields = set()
        meta: LoaderQueryMeta = {
            'fields': [],
            'request_types': []
        }

        for tt in types:
            for t in tt:
                fields = _get_all_fields(t)
                meta['request_types'].append(dict(name=t, fields=fields))
                _fields.update(fields)
        meta['fields'] = list(_fields)
        return meta
    
    cache = {}
    request_info = {}
    
    # create instance
    for loader in _get_all_loaders_from_meta(metadata):
        loader_kls, path = loader['kls'], loader['path']

        if path in cache: continue

        if loader_instances.get(loader_kls):  # if instance already exists
            cache[path] = loader_instances.get(loader_kls)
            continue

        cache[path] = _create_instance(loader)    

    # prepare query meta
    for loader in _get_all_loaders_from_meta(metadata):
        kls, path = loader['request_type'], loader['path']

        if kls is None:
            continue

        if path in request_info and kls not in request_info[path]:
            request_info[path].append(kls)
        else: 
            request_info[path] = [kls]

    # combine together
    for path, instance in cache.items():
        if request_info.get(path) is None:
            continue

        instance._query_meta = _generate_meta(request_info[path])

    return cache


def scan_and_store_metadata(root_class: Type) -> MetaType:

    class_util.update_forward_refs(root_class)
    expose_set = set()  # for validation
    collect_set = set()  # for validation
    metadata: MetaType = {}

    def _get_request_type_for_loader(object_field_pairs, field_name: str):
        return object_field_pairs.get(field_name)

    def _get_all_fields_and_object_fields(kls):
        if class_util.safe_issubclass(kls, BaseModel):
            all_fields = set(class_util.get_pydantic_field_keys(kls))
            object_fields = list(class_util.get_pydantic_fields(kls))  # dive and recursively analysis
        elif is_dataclass(kls):
            all_fields = set([f.name for f in dc_fields(kls)])
            object_fields = list(class_util.get_dataclass_fields(kls))
        else:
            raise AttributeError('invalid type: should be pydantic object or dataclass object')  #noqa
        return all_fields, object_fields, { x:y for x, y in object_fields}
    
    def _has_post_default_handler(kls):
        fields = dir(kls)
        fields = [f for f in fields if f == const.POST_DEFAULT_HANDLER and isfunction(getattr(kls, f))]
        return len(fields) > 0

    def _get_resolve_and_post_fields(kls):
        fields = dir(kls)

        resolve_fields = [f for f in fields if f.startswith(const.RESOLVE_PREFIX) and isfunction(getattr(kls, f))]
        post_fields = [f for f in fields if f.startswith(const.POST_PREFIX) 
                                                and f != const.POST_DEFAULT_HANDLER
                                                and isfunction(getattr(kls, f))]
        fields_with_resolver = { field.replace(const.RESOLVE_PREFIX, '') for field in resolve_fields }
        return resolve_fields, post_fields, fields_with_resolver
    
    def _validate_resolve_and_post_fields(resolve_fields, post_fields, all_fields):
        for field in resolve_fields:
            resolve_field = field.replace(const.RESOLVE_PREFIX, '')
            if resolve_field not in all_fields:
                raise ResolverTargetAttrNotFound(f"attribute {resolve_field} not found")

        for field in post_fields:
            post_field = field.replace(const.POST_PREFIX, '')
            if post_field not in all_fields:
                raise ResolverTargetAttrNotFound(f"attribute {post_field} not found")

    def _validate_expose(expose_dict, kls_name):
        if type(expose_dict) is not dict:
            raise AttributeError(f'{const.EXPOSE_TO_DESCENDANT} is not dict')
        for _, v in expose_dict.items():
            if v in expose_set:
                raise AttributeError(f'Expose alias name conflicts, please check: {kls_name}')
            expose_set.add(v)
    
    def _add_collector_info(post_params):
        for _, param in post_params.items():
            for collector in param['collectors']:
                collect_set.add(collector['alias'])

    def _add_collector_info_for_default_handler(post_default_params):
        if post_default_params is not None:
            for collector in post_default_params['collectors']:
                collect_set.add(collector['alias'])

    def _validate_collector(collect_dict, kls_name):
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
                if c not in collect_set:
                    raise MissingCollector(f'Collector alias name not found in ancestor, please check: {kls_name}')
    
    def _has_config(info: KlsMetaType):
        result = len(info['resolve']) > 0 or \
                len(info['post']) > 0 or \
                len(info['collect_dict']) > 0 or \
                len(info['expose_dict']) > 0 or \
                info['post_default_handler_params'] is not None
        return result

    def _populate_ancestors(parents):
        for field, kls_name in parents:
            # normally, array size is small
            if field in metadata[kls_name]['raw_object_fields'] and \
                field not in metadata[kls_name]['object_fields']:
                metadata[kls_name]['object_fields'].append(field)
            metadata[kls_name]['should_traverse'] = True

    def walker(kls, ancestors: List[Tuple[str, str]]):
        kls_name = class_util.get_kls_full_name(kls)
        hit = metadata.get(kls_name)
        if hit:
            # if populated by previous node, or self has_config
            if hit['should_traverse'] or _has_config(hit):
                _populate_ancestors(ancestors)
            return

        # - prepare fields, with resolve_, post_ reserved
        all_fields, object_fields, object_field_pairs = _get_all_fields_and_object_fields(kls)
        resolve_fields, post_fields, fields_with_resolver = _get_resolve_and_post_fields(kls)
        _validate_resolve_and_post_fields(resolve_fields, post_fields, all_fields)
        object_fields_without_resolver = [a[0] for a in object_fields if a[0] not in fields_with_resolver] 

        # - scan expose and collect (__pydantic_resolve_xxx__)
        expose_dict = getattr(kls, const.EXPOSE_TO_DESCENDANT, {})
        collect_dict = getattr(kls, const.COLLECTOR_CONFIGURATION, {})
        _validate_expose(expose_dict, kls_name)

        resolve_params = {
            field: _scan_resolve_method(
                    getattr(kls, field),
                    field,
                    _get_request_type_for_loader(
                        object_field_pairs, 
                        field.replace(const.RESOLVE_PREFIX, ''))) 
                for field in resolve_fields
        }
        post_params = {
            field: _scan_post_method(
                    getattr(kls, field),
                    field,
                    _get_request_type_for_loader(
                        object_field_pairs, 
                        field.replace(const.POST_PREFIX, ''))) 
                for field in post_fields
        }
        post_default_handler_params = _scan_post_default_handler(getattr(kls, const.POST_DEFAULT_HANDLER)) if _has_post_default_handler(kls) else None

        # check context
        resolve_context = any([p['context'] for p in resolve_params.values()])
        post_context = any([p['context'] for p in post_params.values()])
        post_default_context = post_default_handler_params['context'] if post_default_handler_params else False
        has_context = resolve_context or post_context or post_default_context

        # check collector
        _add_collector_info(post_params)
        _add_collector_info_for_default_handler(post_default_handler_params)
        _validate_collector(collect_dict, kls_name)

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
        metadata[kls_name] = info

        # object fields
        for field, shelled_types in (obj for obj in object_fields if obj[0] in object_fields_without_resolver):
            for shelled_type in shelled_types:
                walker(shelled_type, ancestors + [(field, kls_name)])

        # resolve fields
        for field, shelled_types in (obj for obj in object_fields if obj[0] in fields_with_resolver):
            for shelled_type in shelled_types:
                walker(shelled_type, ancestors + [(field, kls_name)])

        should_traverse = info['should_traverse'] or _has_config(info)

        if should_traverse:
            _populate_ancestors(ancestors)

        info['should_traverse'] = should_traverse

    walker(root_class, [])
    return metadata


def convert_metadata_key_as_kls(metadata: MetaType) -> MappedMetaType:
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


def _calc_alias_map_from_collectors(kls_meta: MappedMetaMemberType):
    post_params = kls_meta['post_params']
    kls_path = kls_meta['kls_path']

    alias_map = defaultdict(dict)

    def add_collector(collector: CollectorType):
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


def is_acceptable_kls(kls: Type) -> bool:
    return class_util.safe_issubclass(kls, BaseModel) or is_dataclass(kls)


def is_acceptable_instance(target: object):
    """ check whether target is Pydantic object or Dataclass object """
    return isinstance(target, BaseModel) or is_dataclass(target)


def get_resolve_fields_and_object_fields_from_object(node: object, kls: Type, mapped_metadata: MappedMetaType):
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


def get_post_methods(node: object, kls: Type, mapped_metadata: MappedMetaType):
    kls_meta = mapped_metadata.get(kls)

    if kls_meta is None:
        return []

    for post_field in kls_meta['post']:
        attr = getattr(node, post_field)
        trim_field = kls_meta['post_params'][post_field]['trim_field']
        yield post_field, trim_field, attr


def get_resolve_method_param(kls: Type, resolve_field: str, mapped_metadata: MappedMetaType):
    kls_meta = mapped_metadata.get(kls, {})
    return kls_meta['resolve_params'][resolve_field]


def get_post_method_params(kls, post_field, mapped_metadata: MappedMetaType):
    kls_meta = mapped_metadata.get(kls, {})
    return kls_meta['post_params'][post_field]


def get_post_default_handler_params(kls, mapped_metadata: MappedMetaType):
    kls_meta = mapped_metadata.get(kls, {})
    return kls_meta['post_default_handler_params']


def get_collector_sign(kls_path: str, collector: CollectorType):
    return (kls_path, collector['field'], collector['param'])


def generate_alias_map_with_cloned_collector(kls: Type, mapped_metadata: MappedMetaType):
    kls_meta = mapped_metadata.get(kls, {})
    return { alias: {
        sign: copy.deepcopy(collector) for sign, collector in v.items()
    } for alias, v in kls_meta['alias_map_proto'].items()}


def get_collector_candidates(kls, metadata: MappedMetaType):
    kls_meta = metadata.get(kls, {})
    collect_dict = kls_meta['collect_dict']

    for field, alias in collect_dict.items():
        yield field, alias


def has_context(mapped_metadata: MappedMetaType):
    return any([ m['has_context'] for m in mapped_metadata.values()])