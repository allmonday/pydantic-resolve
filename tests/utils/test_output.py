from pydantic_resolve.util import output
from pydantic import BaseModel

def test_output():
    @output
    class A(BaseModel):
        name: str = ''
        age: int = 0
    
    assert A.__fields__['name'].required == True
    assert A.__fields__['age'].required == True