from pydantic import BaseModel
from pydantic_resolve.utils.er_diagram import base_entity, Relationship

Base = base_entity()

class Sub(BaseModel):
    id: int
    name: str

class MyModel(BaseModel, Base):
    __pydantic_resolve_relationships__ = [
        Relationship(field='id', target_kls=Sub, loader=None)
    ]
    id: int

class MyModelSub(MyModel):
    id: int

class AnotherModel(BaseModel, Base):
    __pydantic_resolve_relationships__ = [
        Relationship(field='id', target_kls=Sub, loader=None)
    ]
    id: int

def test_bases():
    assert MyModel in Base.entities
    assert AnotherModel in Base.entities
    assert MyModelSub not in Base.entities
    assert len(Base.entities) == 2
