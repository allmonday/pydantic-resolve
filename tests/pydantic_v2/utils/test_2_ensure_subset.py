from dataclasses import dataclass
from typing import Optional
from pydantic import BaseModel
from pydantic_resolve.utils import class_util
import pytest

def test_ensure_subset():
    class Base(BaseModel):
        a: str
        b: int

    @dataclass
    class BaseX():
        a: str
        b: int
    
    @class_util.ensure_subset(Base)
    class ChildA(BaseModel):
        a: str

    @class_util.ensure_subset(Base)
    class ChildB(BaseModel):
        a: str
        c: int = 0
        def resolve_c(self):
            return 21

    @class_util.ensure_subset(Base)
    class ChildB1(BaseModel):
        a: str
        d: Optional[int] = 0

    with pytest.raises(AttributeError):
        @class_util.ensure_subset(Base)
        class ChildC(BaseModel):
            a: str
            b: str

    with pytest.raises(AttributeError):
        @class_util.ensure_subset(Base)
        class ChildD(BaseModel):
            a: str
            b: int
            c: int

    with pytest.raises(TypeError):
        @class_util.ensure_subset(Base)
        @dataclass
        class ChildE():
            a: str
            b: int
            c: int


def test_ensure_subset_dataclass():
    @dataclass
    class Base:
        a: str
        b: int

    @class_util.ensure_subset(Base)
    @dataclass
    class ChildA:
        a: str

    @class_util.ensure_subset(Base)
    @dataclass
    class ChildB:
        a: str
        c: int = 0
        def resolve_c(self):
            return 21

    @class_util.ensure_subset(Base)
    @dataclass
    class ChildB1:
        a: str
        d: Optional[int]

    with pytest.raises(AttributeError):
        @class_util.ensure_subset(Base)
        @dataclass
        class ChildC:
            x: str
            y: str

    with pytest.raises(AttributeError):
        @class_util.ensure_subset(Base)
        @dataclass
        class ChildD:
            x: str
            y: int
            z: int


    with pytest.raises(TypeError):
        @class_util.ensure_subset(Base)
        class ChildE(BaseModel):
            a: str
            b: int
            c: int
