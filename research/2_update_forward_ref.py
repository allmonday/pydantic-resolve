from __future__ import annotations
import time
from collections import namedtuple
from typing import List, Optional
from pydantic import parse_obj_as, BaseModel

"""
if using annotations
type should call update_forward_refs to find the real type.
"""

def forwrad(kls: BaseModel):
    kls.update_forward_refs()
    for f, field in kls.__fields__.items():
        if issubclass(field.type_, BaseModel):
            forwrad(field.type_)

DD = namedtuple('DD', 'name')

class Base(BaseModel):
    count: int

class A(BaseModel):
    name: str
    b: Optional[B]

class B(BaseModel):
    name: str
    c: List[C] = []

class C(Base):
    name: str
    d: Optional[D] = None

class D(BaseModel):
    name: str

    class Config:
        orm_mode = True

forwrad(A)

c = parse_obj_as(A,{'name': 'a', 'b': {'name': 'ki', 'c': [{'name': '1', 'count': 1, 'd': DD(name='d')}]}})
print(c)

c = parse_obj_as(B, c)
print(c)