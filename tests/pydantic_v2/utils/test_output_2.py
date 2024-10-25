from dataclasses import dataclass
from pydantic_resolve.util import output
from pydantic import BaseModel
from typing import List, Optional
import pytest

def test_output_will_not_affect_other():

    @output
    class X(BaseModel):
        id: int
        name: str

    class A(BaseModel):
        id: int
        opt: Optional[str] = None

        name: str = ''
        def resolve_name(self):
            return 'hi'

        age: int = 0
        def resolve_age(self):
            return 1

        greet: str = ''
        def post_greet(self):
            return 'hi'
    
    json_schema = A.model_json_schema()
    assert set(json_schema['required']) == {'id'}

    a = A(id=1)
    assert a.id == 1  # can assign

