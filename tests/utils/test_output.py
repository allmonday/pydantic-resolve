from dataclasses import dataclass
from pydantic_resolve.util import output
from pydantic import BaseModel
import pytest

def test_output():
    @output
    class A(BaseModel):
        name: str = ''
        age: int = 0
    
    assert A.__fields__['name'].required == True
    assert A.__fields__['age'].required == True

def test_output2():

    with pytest.raises(AttributeError):
        @output
        @dataclass
        class A():
            name: str = ''
            age: int = 0