import inspect
from inspect import isfunction, isclass
from typing import Any, Callable, Optional
from aiodataloader import DataLoader
from pydantic import BaseModel
from dataclasses import is_dataclass, fields as dc_fields
from typing import TypeVar
import pydantic_resolve.util as util
import pydantic_resolve.constant as const
from .exceptions import ResolverTargetAttrNotFound, LoaderFieldNotProvidedError

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


def _scan_resolve_method(method):
    result = {
        'context': False,
        'ancestor_context': False,
        'dataloaders': []  # collect func or class, do not create instance
    }
    signature = inspect.signature(method)

    if signature.parameters.get('context'):
        result['context'] = True

    if signature.parameters.get('ancestor_context'):
        result['ancestor_context'] = True

    for k, v in signature.parameters.items():
        if isinstance(v.default, Depends):
            info = { 
                'param': k,
                'kls': v.default.dependency,  # for later initialization
                'path': util.get_kls_full_path(v.default.dependency) }
            result['dataloaders'].append(info)
    return result


def _scan_post_method(method):
    result = {
        'context': False,
        'ancestor_context': False,
    }
    signature = inspect.signature(method)

    if signature.parameters.get('context'):
        result['context'] = True

    if signature.parameters.get('ancestor_context'):
        result['ancestor_context'] = True
            
    return result


def _validate_and_create_instance(
        loader_params,
        global_loader_param,
        loader_instances,
        meta):
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
    def _get_all_loaders_from_meta(meta):
        for kls_name, kls_info in meta.items():
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
    
    for loader in _get_all_loaders_from_meta(meta):
        # check
        # - cache exists
        # - from loader_instance
        # - create_instance
        loader_kls, path = loader['kls'], loader['path']
        if path in cache:
            continue

        if loader_instances.get(loader_kls):
            cache[path] = loader_instances.get(loader_kls)
            continue
            
        cache[path] = _create_instance(loader)    

    return cache

                    


def scan_and_store_metadata(root_class):
    """
    see:
    - test_field_dataclass_anno.py
    - test_field_pydantic.py

    metadata:
    - resolve
    - resolve_params
        - [resolve_field]
            - context
            - ancestor_context
            - dataloaders
                - param
                - kls
                - path
    - post
    - post_params
        - [post_field]
            - context
            - ancestor_context
            - collector (TBD)
    - attribute
    - expose_dict
    - collect_dict

    rules:
    - dataloader and it's params
    - context & ancestor_context are provided
    - collector should be defined in ancestor of collect schemas.
    """

    util.update_forward_refs(root_class)
    expose_set = set()
    collect_set = set()
    metadata = {}


    def walker(kls):
        """
        1. collect fields
            1.1 validate context and 
        2. collect expose and 'collect'
        """
        kls_name = util.get_kls_full_path(kls)
        hit = metadata.get(kls_name)
        if hit: return

        fields_with_resolver = set()  # resolve_name --> name
        fields = dir(kls)

        resolve_fields = [f for f in fields if f.startswith(const.PREFIX) and isfunction(getattr(kls, f))]
        post_fields = [f for f in fields if f.startswith(const.POST_PREFIX) 
                                                and f != const.POST_DEFAULT_HANDLER
                                                and isfunction(getattr(kls, f))]

        # get all fields and object fields
        if issubclass(kls, BaseModel):
            all_fields = set(kls.__fields__.keys())
            object_fields = list(_get_pydantic_attrs(kls))  # dive and recursively analysis
        elif is_dataclass(kls):
            all_fields = set([f.name for f in dc_fields(kls)])
            object_fields = list(_get_dataclass_attrs(kls))
        else:
            raise AttributeError('invalid type: should be pydantic object or dataclass object')  #noqa

        # validate resolve target field
        for field in resolve_fields:
            resolve_field = field.replace(const.PREFIX, '')
            if resolve_field not in all_fields:
                raise ResolverTargetAttrNotFound(f"attribute {resolve_field} not found")
            fields_with_resolver.add(resolve_field)

        # validate post target field
        for field in post_fields:
            post_field = field.replace(const.POST_PREFIX, '')
            if post_field not in all_fields:
                raise ResolverTargetAttrNotFound(f"attribute {post_field} not found")

        object_fields_without_resolver = [a[0] for a in object_fields if a[0] not in fields_with_resolver] 

        # <-- start of validate expose and collect
        expose_dict = getattr(kls, const.EXPOSE_TO_DESCENDANT, {})
        collect_dict = getattr(kls, const.COLLECT_FROM_ANCESTOR, {})

        if type(expose_dict) is not dict:
            raise AttributeError(f'{const.EXPOSE_TO_DESCENDANT} is not dict')
        for _, v in expose_dict.items():
            if v in expose_set:
                raise AttributeError(f'expose alias name conflicts, please check: {kls_name}')
            expose_set.add(v)

        if type(collect_dict) is not dict:
            raise AttributeError(f'{const.COLLECT_FROM_ANCESTOR} is not dict')
        for _, v in collect_dict.items():
            if v in collect_set:
                raise AttributeError(f'collect alias name conflicts, please check: {kls_name}')
            collect_set.add(v)
        # end of validate expose and collect -->

        resolve_params = {
            field: _scan_resolve_method(getattr(kls, field)) for field in resolve_fields
        }
        post_params = {
            field: _scan_post_method(getattr(kls, field)) for field in post_fields
        }

        metadata[kls_name] = {
            'resolve': resolve_fields,
            'resolve_params': resolve_params,
            'post': post_fields,
            'post_params': post_params,
            'attribute': object_fields_without_resolver,
            'expose_dict': expose_dict,
            'collect_dict': collect_dict
        }

        for _, shelled_type in object_fields:
            walker(shelled_type)

    walker(root_class)
    return metadata

def is_acceptable_kls(kls):
    return issubclass(kls, BaseModel) or is_dataclass(kls)

def is_acceptable_instance(target):
    """ check whether target is Pydantic object or Dataclass object """
    return isinstance(target, BaseModel) or is_dataclass(target)

def iter_over_object_resolvers_and_acceptable_fields(target, attr_map):
    kls = get_class(target)
    attr_info = attr_map.get(util.get_kls_full_path(kls))

    resolve, attribute = [], []

    for attr_name in attr_info['resolve']:
        attr = getattr(target, attr_name)
        resolve.append((attr_name, attr))

    for attr_name in attr_info['attribute']:
        attr = getattr(target, attr_name)
        attribute.append((attr_name, attr))

    return resolve, attribute

def iter_over_object_post_methods(target, attr_map):
    """get method starts with post_"""
    kls = get_class(target)
    attr_info = attr_map.get(util.get_kls_full_path(kls))

    for attr_name in attr_info['post']:
        yield attr_name

