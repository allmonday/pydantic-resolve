from dataclasses import dataclass
from pydantic_resolve.util import output
from pydantic import BaseModel
from typing import List, Optional
import pytest

def test_output():
    @output
    class A(BaseModel):
        id: int
        opt: Optional[str]

        name: str = ''
        def resolve_name(self):
            return 'hi'

        age: int = 0
        def resolve_age(self):
            return 1

        greet: str = ''
        def post_greet(self):
            return 'hi'
    
    json_schema = A.schema()
    assert set(json_schema['required']) == {'id', 'name', 'age', 'greet'}

    a = A(id=1)
    assert a.id == 1  # can assign


def test_output2():

    with pytest.raises(AttributeError):
        @output
        @dataclass
        class A():
            name: str
            age: int


def test_output_3():
    
    class B(BaseModel):
        id: int 

    class ABase(BaseModel):
        id: int

    @output
    class A(ABase):
        name: List[str] = [] 
        def resolve_name(self):
            return ['hi']

        age: int = 0
        def resolve_age(self):
            return 1
        
        bs: List[B] = []
        def resolve_bs(self):
            return []
    
    json_schema = A.schema()
    assert set(json_schema['required']) == {'id', 'name', 'age', 'bs'}

