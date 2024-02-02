from pydantic_resolve.util import output
from pydantic import BaseModel
from typing import Optional

def test_output():
    """
    output will not affect other class
    """
    @output
    class X(BaseModel):
        id: int
        opt: Optional[str]

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
    assert set(json_schema['required']) == {'id'}
