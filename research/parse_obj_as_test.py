from pydantic import parse_obj_as, BaseModel
from timeit import timeit

class Y(BaseModel):
    name: str

class X(BaseModel):
    name: str
    y: Y

class A(BaseModel):
    name: str
    x: X

a = A(name='a', x=X(name='x', y=Y(name='y')))

def test_a():
    parse_obj_as(A, {'name': 'a', 'x': {'name': 'x', 'y': {'name': 'y'}}})


def test_b():
    parse_obj_as(A, a)

print(timeit(test_a, number=100000))
print(timeit(test_b, number=100000))


b = parse_obj_as(A, a)
print(id(b.x) == id(a.x))