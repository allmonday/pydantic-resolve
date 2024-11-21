from typing import Type, Union
from pydantic_resolve.compat import PYDANTIC_V2


def _is_optional(annotation):
    annotation_origin = getattr(annotation, "__origin__", None)
    return annotation_origin == Union \
        and len(annotation.__args__) == 2 \
        and annotation.__args__[1] == type(None)  # noqa


def _is_list(annotation):
    return getattr(annotation, "__origin__", None) == list


def shelling_type(type):
    while _is_optional(type) or _is_list(type):
        type = type.__args__[0]
    return type


def get_class_field_annotations(cls: Type):
    anno = cls.__dict__.get('__annotations__') or {}
    return anno.keys()


def _get_type_v1(v):
    return v.type_


def _get_type_v2(v):
    return v.annotation


get_type = _get_type_v2 if PYDANTIC_V2 else _get_type_v1