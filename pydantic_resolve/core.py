import abc
import copy
import inspect
from inspect import isfunction, isclass
from collections import defaultdict
from typing import Any, Callable, Optional
from aiodataloader import DataLoader
from pydantic import BaseModel
from dataclasses import is_dataclass, fields as dc_fields
import pydantic_resolve.util as util
import pydantic_resolve.constant as const
from .exceptions import ResolverTargetAttrNotFound, LoaderFieldNotProvidedError, MissingCollector

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

class ICollector(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def __init__(self, alias: str):
        self.alias = alias  # required, must have

    @abc.abstractmethod
    def add(self, val):
        """how to add new element(s)"""

    @abc.abstractmethod
    def values(self) -> Any:
        """get result"""

class Collector(ICollector):
    def __init__(self, alias: str, flat: bool=False):
        self.alias = alias
        self.flat = flat
        self.val = []
    
    def add(self, val):
        if self.flat:
            if isinstance(val, list):
                self.val.extend(val)
            else:
                raise AttributeError('if flat, target should be list')
        else:
            self.val.append(val)

    def values(self):
        return self.val


def _get_pydantic_attrs(kls):
    for k, v in kls.__fields__.items():
        shelled_type = util.shelling_type(v.type_)
        if is_acceptable_kls(shelled_type):
            yield (k, shelled_type)  # type_ is the most inner type


def _get_dataclass_attrs(kls):
    for name, v in kls.__annotations__.items():
        shelled_type = util.shelling_type(v)
        if is_acceptable_kls(shelled_type):
            yield (name, shelled_type)


def get_class(target):
    if isinstance(target, list):
        return target[0].__class__
    else:
        return target.__class__


def _scan_resolve_method(method, field: str):
    result = {
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
            info = { 
                'param': name,
                'kls': param.default.dependency,  # for later initialization
                'path': util.get_kls_full_path(param.default.dependency) }
            result['dataloaders'].append(info)

    for name, param in signature.parameters.items():
        if isinstance(param.default, ICollector):
            raise AttributeError("Collector is not available in resolve_method")

    return result


def _scan_post_method(method, field):
    result = {
        'trim_field': field.replace(const.POST_PREFIX, ''),
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
            info = {
                'field': field,
                'param': name,
                'instance': param.default,
                'alias': param.default.alias 
            }
            result['collectors'].append(info)
            
    return result


def _scan_post_default_handler(method):
    result = {
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
            info = {
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
        metadata):
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
        for kls, kls_info in metadata.items():
            for resolve_field, resolve_info in kls_info['resolve_params'].items():
                for loader in resolve_info['dataloaders']:
                    # param, kls, path
                    yield loader
    
    def _create_instance(loader):
        """
        1. is class?
            - validate params
        2. is func """
        loader_kls, path = loader['kls'], loader['path']
        if isclass(loader_kls):
            loader = loader_kls()
            param_config = util.merge_dicts(
                global_loader_param,
                loader_params.get(loader_kls, {}))

            for field in util.get_class_field_annotations(loader_kls):
                try:
                    value = param_config[field]
                    setattr(loader, field, value)
                except KeyError:
                    raise LoaderFieldNotProvidedError(f'{path}.{field} not found in Resolver()')
            return loader
        else:
            loader = DataLoader(batch_load_fn=loader_kls)  # type:ignore
            return loader
    
    cache = {}
    
    for loader in _get_all_loaders_from_meta(metadata):
        loader_kls, path = loader['kls'], loader['path']

        if path in cache: continue
        if loader_instances.get(loader_kls):
            cache[path] = loader_instances.get(loader_kls)
            continue
        cache[path] = _create_instance(loader)    

    return cache


def scan_and_store_metadata(root_class):
    """ see output data schema example in:
    - test_field_dataclass_anno.py
    - test_field_pydantic.py

    rules: TODO:
    - [x] dataloader and it's params
    - [ ] context & ancestor_context are provided
    - [ ] collector should be defined in ancestor of collect schemas.  """
    util.update_forward_refs(root_class)
    expose_set = set()  # for validation
    collect_set = set()  # for validation
    metadata = {}

    def _get_all_fields_and_object_fields(kls):
        if util.safe_issubclass(kls, BaseModel):
            all_fields = set(kls.__fields__.keys())
            object_fields = list(_get_pydantic_attrs(kls))  # dive and recursively analysis
        elif is_dataclass(kls):
            all_fields = set([f.name for f in dc_fields(kls)])
            object_fields = list(_get_dataclass_attrs(kls))
        else:
            raise AttributeError('invalid type: should be pydantic object or dataclass object')  #noqa
        return all_fields, object_fields
    
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
        """collector should be declared in ancestors"""
        if type(collect_dict) is not dict:
            raise AttributeError(f'{const.COLLECT_FROM_ANCESTOR} is not dict')

        for _, collector in collect_dict.items():
            colls = collector if isinstance(collector, (list, tuple)) else (collector,)
            for col in colls:
                if col not in collect_set:
                    raise MissingCollector(f'Collector alias name not found in ancestor, please check: {kls_name}')

    def walker(kls):
        kls_name = util.get_kls_full_path(kls)
        hit = metadata.get(kls_name)
        if hit: return

        # - prepare fields, with resolve_, post_ reserved
        all_fields, object_fields = _get_all_fields_and_object_fields(kls)
        resolve_fields, post_fields, fields_with_resolver = _get_resolve_and_post_fields(kls)
        _validate_resolve_and_post_fields(resolve_fields, post_fields, all_fields)
        object_fields_without_resolver = [a[0] for a in object_fields if a[0] not in fields_with_resolver] 

        # - scan expose and collect (__pydantic_resolve_xxx__)
        expose_dict = getattr(kls, const.EXPOSE_TO_DESCENDANT, {})
        collect_dict = getattr(kls, const.COLLECT_FROM_ANCESTOR, {})
        _validate_expose(expose_dict, kls_name)

        resolve_params = {field: _scan_resolve_method(getattr(kls, field), field) for field in resolve_fields}
        post_params = {field: _scan_post_method(getattr(kls, field), field) for field in post_fields}
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

        metadata[kls_name] = {
            'resolve': resolve_fields,
            'resolve_params': resolve_params,
            'post': post_fields,
            'post_params': post_params,
            'post_default_handler_params': post_default_handler_params,
            'attribute': object_fields_without_resolver,
            'expose_dict': expose_dict,
            'collect_dict': collect_dict,
            'kls': kls,
            'has_context': has_context,
        }

        for _, shelled_type in object_fields:
            walker(shelled_type)

    walker(root_class)
    return metadata


def convert_metadata_key_as_kls(metadata):
    """ use kls as map key for performance """
    kls_metadata = {}
    for k, v in metadata.items():
        v['kls_path'] = k
        kls_metadata[v['kls']] = v
    
    return kls_metadata


def is_acceptable_kls(kls):
    return util.safe_issubclass(kls, BaseModel) or is_dataclass(kls)


def is_acceptable_instance(target):
    """ check whether target is Pydantic object or Dataclass object """
    return isinstance(target, BaseModel) or is_dataclass(target)


def iter_over_object_resolvers_and_acceptable_fields(target, kls, metadata):
    """metadata key is kls"""
    kls_meta = metadata.get(kls)

    resolve, attribute = [], []

    for resolve_field in kls_meta['resolve']:  # eg: resolve_name
        attr = getattr(target, resolve_field)
        trim_field = kls_meta['resolve_params'][resolve_field]['trim_field']
        resolve.append((resolve_field, trim_field, attr))

    for attr_name in kls_meta['attribute']:
        attr = getattr(target, attr_name)
        attribute.append((attr_name, attr))

    return resolve, attribute


def iter_over_object_post_methods(kls, metadata):
    """metadata key is kls"""
    kls_meta = metadata.get(kls)

    for post_field in kls_meta['post']:
        trim_field = kls_meta['post_params'][post_field]['trim_field']
        yield post_field, trim_field


def get_resolve_param(kls, resolve_field, metadata):
    kls_meta = metadata.get(kls, {})
    return kls_meta['resolve_params'][resolve_field]


def get_post_params(kls, post_field, metadata):
    kls_meta = metadata.get(kls, {})
    return kls_meta['post_params'][post_field]


def get_post_default_handler_params(kls, metadata):
    kls_meta = metadata.get(kls, {})
    return kls_meta['post_default_handler_params']


def get_collectors(kls, metadata):
    kls_meta = metadata.get(kls, {})

    # post method
    post_params = kls_meta['post_params']
    kls_path = kls_meta['kls_path']

    alias_map = defaultdict(dict)
    for _, param in post_params.items():
        for collector in param['collectors']:
            sign = (kls_path, collector['field'], collector['param'])
            # copied instance will be stored in resolver's self.object_collect_alias_map_store
            alias_map[collector['alias']][sign] = copy.deepcopy(collector['instance'])

    # post_default_handler
    post_default_handler_params = kls_meta['post_default_handler_params']
    if post_default_handler_params:
        for collector in post_default_handler_params['collectors']:
            sign = (kls_path, collector['field'], collector['param'])
            alias_map[collector['alias']][sign] = copy.deepcopy(collector['instance'])

    return alias_map


def iter_over_collectable_fields(kls, metadata):
    kls_meta = metadata.get(kls, {})
    collect_dict = kls_meta['collect_dict']

    for field, alias in collect_dict.items():
        yield field, alias


def has_context(metadata):
    return any([ m['has_context'] for m in metadata.values()])