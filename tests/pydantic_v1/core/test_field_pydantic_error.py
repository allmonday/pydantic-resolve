from __future__ import annotations
import pytest
from typing import Optional
from pydantic import BaseModel
from pydantic_resolve.core import scan_and_store_metadata

class A(BaseModel):
    __pydantic_resolve_expose__ = {'name': 'A_name'}
    name: str = ''
    b: Optional[B] = None
    def resolve_b(self):
        return dict(name='b')

class B(BaseModel):
    __pydantic_resolve_expose__ = {'name': 'A_name'}
    name: str
    c: Optional[C] = None
    def resolve_c(self):
        return dict(name='c')

class C(BaseModel):
    name: str


def test_raise_exception():
    with pytest.raises(AttributeError):
        scan_and_store_metadata(A)