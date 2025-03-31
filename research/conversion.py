from pydantic import TypeAdapter
from pydantic import BaseModel
import time

class A(BaseModel):
    name: str
    id: int
    name2: str
    name3: str
    name4: str
    name5: str
    name6: str 
    name7: str


at = TypeAdapter(A)

def test_type_adapter():
    t = time.time()
    for i in range(1000000):
        result = at.validate_python(
            {'name': 'name-1', 'id': 1, 'name2': 'name-2', 'name3': 'name-3', 'name4': 'name-4', 'name5': 'name-5', 'name6': 'name-6', 'name7': 'name-7'},
            from_attributes=True
        )
        # assert result.id == 1
        # assert result.name == 'name-1' 
    t2 = time.time() - t
    print(t2)

    t = time.time()
    for i in range(1000000):
        result = at.validate_python(
            {'name': 'name-1', 'id': 1, 'name2': 'name-2', 'name3': 'name-3', 'name4': 'name-4', 'name5': 'name-5', 'name6': 'name-6', 'name7': 'name-7'},
        )
        # assert result.id == 1
        # assert result.name == 'name-1' 
    t2 = time.time() - t
    print(t2)

    # although the result is the same, from_attribute will take more time, about 10+% more time
    assert True



