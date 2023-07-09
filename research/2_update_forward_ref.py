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
        print(f)
        print(field.type_)

        if issubclass(field.type_, BaseModel):
            forwrad(field.type_)

DD = namedtuple('DD', 'name')


class A(BaseModel):
    name: str
    a: Optional[A]
    b: Optional[B]

class B(BaseModel):
    name: str
    c: List[C] = []

class C(BaseModel):
    name: str
    d: Optional[D] = None

class D(BaseModel):
    name: str

    class Config:
        orm_mode = True

forwrad(B)

# acts like
# B.update_forward_refs()
# C.update_forward_refs()

t = time.time()
c = parse_obj_as(B, {'name': 'ki', 'c': [{'name': '1', 'd': DD(name='d')}]})
print(time.time() - t)
c = parse_obj_as(B, c)
print(time.time() - t)
print(c)