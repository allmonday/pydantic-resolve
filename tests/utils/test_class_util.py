from pydantic import BaseModel
from pydantic_resolve.utils.class_util import is_compatible_type
from pydantic_resolve.utils.subset import DefineSubset
from typing import List, Optional

class A(BaseModel):
    id: int
    name: str

class XA(BaseModel):
    id: int
    name: str

class SubA(DefineSubset):
    __pydantic_resolve_subset__ = (A, ['id'])

class SubSubA(DefineSubset):
    __pydantic_resolve_subset__ = (SubA, ['id'])

class SA(A):
    pass

class SSA(SA):
    pass

def test_is_compatible_type():

    assert is_compatible_type(int, str) is False
    assert is_compatible_type(XA, A) is False
    assert is_compatible_type(SubA, XA) is False

    assert is_compatible_type(int, int) is True
    assert is_compatible_type(Optional[int], int) is True
    assert is_compatible_type(Optional[SubA], A) is True

    assert is_compatible_type(SubA, A) is True
    assert is_compatible_type(SubSubA, A) is True

    assert is_compatible_type(List[SubA], List[A]) is True
    assert is_compatible_type(list[SubA], list[A]) is True

    assert is_compatible_type(SA, A) is True
    assert is_compatible_type(SSA, A) is True