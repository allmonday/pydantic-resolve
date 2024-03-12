from inspect import isfunction
from pydantic import BaseModel
from dataclasses import is_dataclass, fields as dc_fields
from typing import TypeVar
import pydantic_resolve.util as util
import pydantic_resolve.constant as const
from .exceptions import ResolverTargetAttrNotFound

# core.py contains all Resolver required functions.

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

def scan_and_store_metadata(root_class):
    """ see test/core/test_field_xxxx.py """

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

        resolver_fields = set()  # resolve_name --> name
        fields = dir(kls)

        raw_resolve_methods = (f for f in fields if f.startswith(const.PREFIX) and isfunction(getattr(kls, f)))
        raw_post_methods = (f for f in fields if f.startswith(const.POST_PREFIX) 
                                                and f != const.POST_DEFAULT_HANDLER
                                                and isfunction(getattr(kls, f)))

        resolve_methods, post_methods = [], []
        attribute_list = []  # all object attributes without resolver
        object_attrs = []  # all attributes of object

        if issubclass(kls, BaseModel):
            all_attrs = set(kls.__fields__.keys())
            object_attrs = list(_get_pydantic_attrs(kls))  # dive and recursively analysis
        elif is_dataclass(kls):
            all_attrs = set([f.name for f in dc_fields(kls)])
            object_attrs = list(_get_dataclass_attrs(kls))
        else:
            raise AttributeError('invalid type: should be pydantic object or dataclass object')  #noqa

        for field in raw_resolve_methods:
            resolve_field = field.replace(const.PREFIX, '')
            if resolve_field not in all_attrs:
                raise ResolverTargetAttrNotFound(f"attribute {resolve_field} not found")
            resolver_fields.add(resolve_field)
            resolve_methods.append(field)

        attribute_list = [a[0] for a in object_attrs if a[0] not in resolver_fields] 

        for field in raw_post_methods:
            post_field = field.replace(const.POST_PREFIX, '')
            if post_field not in all_attrs:
                raise ResolverTargetAttrNotFound(f"attribute {post_field} not found")
            post_methods.append(field)

        # validate expose and collect
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

        metadata[kls_name] = {
            'resolve': resolve_methods,
            'post': post_methods,
            'attribute': attribute_list,
            'expose_dict': expose_dict,
            'collect_dict': collect_dict
        }

        for _, shelled_type in object_attrs:
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

