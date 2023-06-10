from pydantic_resolve import util
from pydantic import BaseModel

def test_get_class_field_annotations():
    class C:
        hello: str

        def __init__(self, c: str):
            self.c = c
        
    class D(C):
        pass

    class E(C):
        world: str
    
    assert list(util.get_class_field_annotations(C)) == ['hello']
    assert list(util.get_class_field_annotations(D)) == []
    assert list(util.get_class_field_annotations(E)) == ['world']


class User(BaseModel):
    id: int
    name: str
    age: int


def test_build_object():
    raw = [(1, 'peter', 10), (2, 'mike', 21), (3, 'john', 12)]
    users = [User(id=i[0], name=i[1], age=i[2]) for i in raw]
    a, b, c = users
    ids = [2, 3, 1, 4]
    output = util.build_object(users, ids, lambda x: x.id)
    assert output == [b, c, a, None]
    

def test_build_list():
    raw = [(1, 'peter', 10), (2, 'mike', 21), (3, 'john', 12)]
    users = [User(id=i[0], name=i[1], age=i[2]) for i in raw]
    a, b, c = users
    ids = [2, 3, 1, 4]
    output = util.build_list(users, ids, lambda x: x.id)
    assert output == [[b], [c], [a], []]