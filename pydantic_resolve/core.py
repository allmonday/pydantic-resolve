from inspect import isfunction, ismethod
from pydantic import BaseModel
from dataclasses import is_dataclass, fields as dc_fields
from typing import TypeVar
from pydantic_resolve.util import get_kls_full_path
from .constant import POSTER, PREFIX, POST_PREFIX, RESOLVER, ATTRIBUTE, POST_DEFAULT_HANDLER
from .util import common_update_forward_refs, shelling_type
from .exceptions import ResolverTargetAttrNotFound

T = TypeVar("T")

def is_list(target) -> bool:
    return isinstance(target, (list, tuple))

def _get_class(target):
    if isinstance(target, list):
        return target[0].__class__
    else:
        return target.__class__

def _get_pydantic_attrs(kls):
    for k, v in kls.__fields__.items():
        if is_acceptable_kls(v.type_):
            yield (k, v.type_)  # type_ is the most inner type

def _get_dataclass_attrs(kls):
    for name, v in kls.__annotations__.items():
        t = shelling_type(v)
        if is_acceptable_kls(t):
            yield (name, t)

def get_all_fields(target):

    root = _get_class(target)

    common_update_forward_refs(root)

    dct = {}

    def walker(kls):
        kls_name = get_kls_full_path(kls)

        hit = dct.get(kls_name)
        if hit:
            return

        resolver_fields = set()
        fields = dir(kls)

        resolvers = [f for f in fields if f.startswith(PREFIX)]
        posts = [f for f in fields if f.startswith(POST_PREFIX)]

        resolve_list = []
        attribute_list = []
        object_list = []
        post_list = []
        if issubclass(kls, BaseModel):
            all_attrs = set(kls.__fields__.keys())
            object_list = list(_get_pydantic_attrs(kls))  # dive and recursively analysis

        elif is_dataclass(kls):
            all_attrs = set([f.name for f in dc_fields(kls)])
            object_list = list(_get_dataclass_attrs(kls))

        else:
            raise AttributeError('invalid type: should be pydantic object or dataclass object')  # noqa

        for field in resolvers:
            attr = getattr(kls, field)
            if isfunction(attr):
                resolve_field = field.replace(PREFIX, '')
                if resolve_field not in all_attrs:
                    raise ResolverTargetAttrNotFound(f"attribute {resolve_field} not found")
                resolver_fields.add(resolve_field)
                resolve_list.append(field)

        attribute_list = [a[0] for a in object_list if a[0] not in resolver_fields]

        for field in posts:
            attr = getattr(kls, field)
            if isfunction(attr) and field != POST_DEFAULT_HANDLER:
                post_field = field.replace(POST_PREFIX, '')
                if post_field not in all_attrs:
                    # raise ResolverTargetAttrNotFound('missing field')  # noqa
                    raise ResolverTargetAttrNotFound(f"attribute {post_field} not found")
                post_list.append(field)

        dct[kls_name] = {
            'resolve': resolve_list,  # to resolve
            'post': post_list,  # to post
            'attribute': attribute_list  # object without resolvable field
        }
        print(dct)

        for obj in object_list:
            print(obj)
            walker(obj[1])

    walker(root)
    return dct

def is_acceptable_kls(kls):
    return issubclass(kls, BaseModel) or is_dataclass(kls)


def is_acceptable_type(target):
    """
    Check whether target is Pydantic object or Dataclass object

    :param target: object
    :type target: BaseModel or Dataclass 
    :rtype: bool

    """
    return isinstance(target, BaseModel) or is_dataclass(target)

def iter_over_object_resolvers_and_acceptable_fields2(target, attr_map):
    ...
    kls = _get_class(target)
    attr_info = attr_map.get(get_kls_full_path(kls))
    pile = []

    for attr_name in attr_info['resolve']:
        attr = target.__getattribute__(attr_name)
        pile.append((attr_name, attr, RESOLVER))

    for attr_name in attr_info['attribute']:
        attr = target.__getattribute__(attr_name)
        pile.append((attr_name, attr, ATTRIBUTE))

    return pile

def iter_over_object_post_methods2(target, attr_map):
    """get method starts with post_"""
    for k in dir(target):
        if k == POST_DEFAULT_HANDLER:  # skip
            continue
        if k.startswith(POST_PREFIX) and ismethod(target.__getattribute__(k)):
            yield k

    kls = _get_class(target)
    attr_info = attr_map.get(get_kls_full_path(kls))
    pile = []
    for attr_name in attr_info['post']:
        pile.append(attr_name)


def iter_over_object_resolvers_and_acceptable_fields(target):
    """
        return 
        1. method starts with resolve_,  eg: resolve_name, resolve_age
        2. field of pydantic or dataclass, which is not resolved by step1. (if `resolve_name` already exists, it will skip `name` )
    """
    resolver_fields = set()
    fields = dir(target)
    resolvers = [f for f in fields if f.startswith(PREFIX)]
    
    pile = []

    if isinstance(target, BaseModel):
        attributes = list(target.__fields__.keys())
    elif is_dataclass(target):
        attributes = [f.name for f in dc_fields(target)]
    else:
        raise AttributeError('invalid type: should be pydantic object or dataclass object')  # noqa

    for field in resolvers:
        attr = target.__getattribute__(field)
        if ismethod(attr):
            resolver_fields.add(field.replace(PREFIX, ''))
            pile.append((field, attr, RESOLVER))

    for field in attributes: 
        if (field in resolver_fields):  # skip field of resolve_[field]
            continue
        attr = target.__getattribute__(field)
        if is_acceptable_type(attr) or is_list(attr):
            pile.append((field, attr, ATTRIBUTE))
    return pile

def iter_over_object_post_methods(target):
    """get method starts with post_"""
    for k in dir(target):
        if k == POST_DEFAULT_HANDLER:  # skip
            continue
        if k.startswith(POST_PREFIX) and ismethod(target.__getattribute__(k)):
            yield k
