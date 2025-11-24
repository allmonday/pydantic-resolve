from __future__ import annotations

from typing import Annotated
from pydantic import BaseModel
from pydantic_resolve.utils.class_util import update_forward_refs
from pydantic_resolve.constant import PYDANTIC_FORWARD_REF_UPDATED

class Base(BaseModel):
    id: int
    name: str

class A(Base):
    b: Annotated[B, "forward ref to B"] 

class B(BaseModel):
    id: int
    name: str
    c: Annotated[C, "forward ref to C"]

class C(BaseModel):
    id: int
    name: str

    
def test_update_forward_refs():
    update_forward_refs(Base)
    assert getattr(Base, PYDANTIC_FORWARD_REF_UPDATED, False) is True

    update_forward_refs(A)

    assert getattr(A, PYDANTIC_FORWARD_REF_UPDATED, False) is True
    assert getattr(A, '__dict__', {}).get(PYDANTIC_FORWARD_REF_UPDATED, False) is True

    assert getattr(B, PYDANTIC_FORWARD_REF_UPDATED, False) is True
    assert getattr(C, PYDANTIC_FORWARD_REF_UPDATED, False) is True