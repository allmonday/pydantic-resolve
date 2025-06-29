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
        d: Optional[int]

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
        class ChildD1():
            a: str
            b: int
            c: int

    with pytest.raises(TypeError):
        @class_util.ensure_subset(BaseX)
        class ChildD2(BaseModel):
            a: str
            b: int
            c: int


def test_ensure_subset_dataclass():
    from pydantic_resolve.utils import class_util

    @dataclass
    class Base:
        a: str
        b: int

    @dataclass
    class ChildA:
        a: str

    @dataclass
    class ChildB:
        a: str
        c: int = 0
        def resolve_c(self):
            return 21

    @dataclass
    class ChildB1:
        a: str
        d: Optional[int]


    # Should not raise
    class_util.ensure_subset(Base)(ChildA)
    class_util.ensure_subset(Base)(ChildB)
    class_util.ensure_subset(Base)(ChildB1)

    with pytest.raises(AttributeError):
        @dataclass
        class ChildC:
            a: str
            b: str  # expect int 
        class_util.ensure_subset(Base)(ChildC)


    with pytest.raises(TypeError):
        class ChildC(BaseModel):  # should not mixed with dataclass
            a: str
            b: int

        class_util.ensure_subset(Base)(ChildC)


    with pytest.raises(AttributeError):
        @dataclass
        class ChildD:
            a: str
            b: int
            c: int  # <- error
            d: Optional[int]
            e: int = 1
        class_util.ensure_subset(Base)(ChildD)
