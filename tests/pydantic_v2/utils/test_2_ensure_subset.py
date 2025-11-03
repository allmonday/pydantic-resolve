from dataclasses import dataclass
from typing import Optional
from pydantic import BaseModel
from pydantic_resolve.utils import class_util
import pydantic_resolve.constant as const
import pytest

def test_ensure_subset():
    class Base(BaseModel):
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

    # Test that ENSURE_SUBSET_REFERENCE is set correctly
    assert hasattr(ChildA, const.ENSURE_SUBSET_REFERENCE)
    assert getattr(ChildA, const.ENSURE_SUBSET_REFERENCE) is Base
    assert hasattr(ChildB, const.ENSURE_SUBSET_REFERENCE)
    assert getattr(ChildB, const.ENSURE_SUBSET_REFERENCE) is Base
    assert hasattr(ChildB1, const.ENSURE_SUBSET_REFERENCE)
    assert getattr(ChildB1, const.ENSURE_SUBSET_REFERENCE) is Base

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

