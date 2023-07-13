from dataclasses import dataclass
from pydantic_resolve.util import output
from pydantic import BaseModel
import pytest

def test_output():
    @output
    class A(BaseModel):
        id: int
        name: str = ''
        def resolve_name(self):
            return 'hi'

        age: int = 0
        def resolve_age(self):
            return 1
    
    json_schema = A.schema()
    assert json_schema['required'] == ['id', 'name', 'age']

    a = A(id=1)
    assert a.id == 1  # can assign


def test_output2():

    with pytest.raises(AttributeError):
        @output
        @dataclass
        class A():
            name: str
            age: int