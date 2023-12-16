from inspect import isfunction
from pydantic import BaseModel
from dataclasses import is_dataclass, fields as dc_fields
from typing import TypeVar
from pydantic_resolve.util import get_kls_full_path
from .constant import PREFIX, POST_PREFIX, POST_DEFAULT_HANDLER
from .util import update_forward_refs, shelling_type
from .exceptions import ResolverTargetAttrNotFound

# core.py contains all Resolver required functions.

T = TypeVar("T")

def _get_class(target):
    if isinstance(target, list):
        return target[0].__class__
    else:
        return target.__class__

def _get_pydantic_attrs(kls):
    for k, v in kls.__fields__.items():
        shelled_type = shelling_type(v.type_)
        if is_acceptable_kls(shelled_type):
            yield (k, shelled_type)  # type_ is the most inner type

def _get_dataclass_attrs(kls):
    for name, v in kls.__annotations__.items():
        shelled_type = shelling_type(v)
        if is_acceptable_kls(shelled_type):
            yield (name, shelled_type)

def scan_and_store_required_fields(target):
    root = _get_class(target)
    update_forward_refs(root)

    scan_result = {}

    def walker(kls):
        kls_name = get_kls_full_path(kls)

        hit = scan_result.get(kls_name)
        if hit:
            return

        resolver_fields = set()  # resolve_name --> name
        fields = dir(kls)

        raw_resolve_methods = (f for f in fields if f.startswith(PREFIX))
        raw_post_methods = (f for f in fields if f.startswith(POST_PREFIX))

        resolve_methods, post_methods = [], []
        attribute_list = []  # all attributes of class without resolve
        object_list = []  # all attributes of class

        if issubclass(kls, BaseModel):
            all_attrs = set(kls.__fields__.keys())
            object_list = list(_get_pydantic_attrs(kls))  # dive and recursively analysis

        elif is_dataclass(kls):
            all_attrs = set([f.name for f in dc_fields(kls)])
            object_list = list(_get_dataclass_attrs(kls))
        else:
            raise AttributeError('invalid type: should be pydantic object or dataclass object')  #noqa

        for field in raw_resolve_methods:
            attr = getattr(kls, field)
            if isfunction(attr):
                resolve_field = field.replace(PREFIX, '')
                if resolve_field not in all_attrs:
                    raise ResolverTargetAttrNotFound(f"attribute {resolve_field} not found")
                resolver_fields.add(resolve_field)
                resolve_methods.append(field)

        attribute_list = [a[0] for a in object_list if a[0] not in resolver_fields]

        for field in raw_post_methods:
            attr = getattr(kls, field)
            if isfunction(attr) and field != POST_DEFAULT_HANDLER:
                post_field = field.replace(POST_PREFIX, '')
                if post_field not in all_attrs:
                    raise ResolverTargetAttrNotFound(f"attribute {post_field} not found")
                post_methods.append(field)

        scan_result[kls_name] = {
            'resolve': resolve_methods,  # to resolve
            'post': post_methods,  # to post
            'attribute': attribute_list  # object without resolvable field
        }

        for obj in object_list:
            walker(obj[1])
    walker(root)

    return scan_result

def is_acceptable_kls(kls):
    return issubclass(kls, BaseModel) or is_dataclass(kls)

def is_acceptable_instance(target):
    """ check whether target is Pydantic object or Dataclass object """
    return isinstance(target, BaseModel) or is_dataclass(target)

def iter_over_object_resolvers_and_acceptable_fields(target, attr_map):
    kls = _get_class(target)
    attr_info = attr_map.get(get_kls_full_path(kls))

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
    kls = _get_class(target)
    attr_info = attr_map.get(get_kls_full_path(kls))

    for attr_name in attr_info['post']:
        yield attr_name

