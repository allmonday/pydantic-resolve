from dataclasses import dataclass
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

    with pytest.raises(AssertionError):
        @class_util.ensure_subset(Base)
        @dataclass
        class ChildD():
            a: str
            b: int
            c: int

    with pytest.raises(AssertionError):
        @class_util.ensure_subset(BaseX)
        @dataclass
        class ChildD():
            a: str
            b: int
            c: int