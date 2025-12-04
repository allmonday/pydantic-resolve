from pydantic import BaseModel
from pydantic_resolve.utils.er_diagram import declarative_base, Relationship

Base = declarative_base()

class Sub(BaseModel):
    id: int
    name: str

class MyModel(BaseModel, Base):
    __pydantic_resolve_relationships__ = [
        Relationship(field='id', target_kls=Sub, loader=None)
    ]
    id: int

class AnotherModel(BaseModel, Base):
    __pydantic_resolve_relationships__ = [
        Relationship(field='id', target_kls=Sub, loader=None)
    ]
    id: int

def test_bases():
    assert MyModel in Base.entities
    assert AnotherModel in Base.entities
    assert len(Base.entities) == 2
