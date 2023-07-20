from __future__ import annotations
from dataclasses import dataclass, field, is_dataclass
from typing import List, Optional, get_type_hints, get_args, Union
from pydantic import parse_obj_as

"""
in contrast to pydantic, dataclass does not need update forward refs
"""

@dataclass
class A():
    name: str
    a: Optional[A]
    b: Optional[B]

@dataclass
class B():
    name: str
    c: List[C] = field(default_factory=list)

@dataclass
class C():
    name: str


def is_optional(annotation):
    annotation_origin = getattr(annotation, "__origin__", None)
    return annotation_origin == Union \
        and len(annotation.__args__) == 2 \
        and annotation.__args__[1] == type(None)  # noqa

def is_list(annotation):
    return getattr(annotation, "__origin__", None) == list

def shelling_type(type):
    while is_optional(type) or is_list(type):
        type = type.__args__[0]
    return type

def update_ref_dc(kls):
    anno = get_type_hints(kls)
    print(anno)
    print(kls.__annotations__)
    kls.__annotations__ = anno
    setattr(kls, '__forward_ref_updated__', True)

    for k, v in kls.__annotations__.items():
        _v = shelling_type(v)
        if is_dataclass(_v):
            if not getattr(_v, '__forward_ref_updated__', None):
                update_ref_dc(_v)


update_ref_dc(A)
print(A.__annotations__['b'])
print(B.__annotations__)