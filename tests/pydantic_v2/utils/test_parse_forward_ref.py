from __future__ import annotations  # which will cause config error
from dataclasses import dataclass
from typing import Optional
from pydantic import ConfigDict, BaseModel, ValidationError
import pytest

def test_dc():
    @dataclass
    class A:
        name: str

    @dataclass
    class B:
        a: A

    b = B(a=A(name='kikodo'))
    assert isinstance(b, B)


def test_parse():
    class B(BaseModel):
        age: int

    class A(BaseModel):
        b: Optional[B] = None 

    a = A.model_validate({'b': {'age': 21}})
    assert isinstance(a, A)

def test_orm():
    class B(BaseModel):
        age: int
        model_config = ConfigDict(from_attributes=True)


    class A(BaseModel):
        b: Optional[B] = None 
        model_config = ConfigDict(from_attributes=True)
    
    class AA:
        def __init__(self, b):
            self.b = b
    class BB:
        def __init__(self, age):
            self.age = age
    
    aa = AA(b=BB(age=21))

    a = A.model_validate(aa)
    assert isinstance(a, A)
