from dataclasses import dataclass, fields, is_dataclass
from pydantic import BaseModel

class O(BaseModel):
    name: str

class A(BaseModel):
    name: str
    o: O

    def resolve_name(self):
        return 'hi'


@dataclass
class B:
    name: str

    def resolve_name(self):
        return '1'
    o: O

# print(A.__fields__)
# print(dir(A))
# print(getattr(A, 'resolve_name'))
# print(getattr(B, 'resolve_name'))
# print(fields(B))
# print(dir(B))

# print(issubclass(A, BaseModel))
# print(is_dataclass(B))

def is_acceptable_kls(kls):
    return issubclass(kls, BaseModel) or is_dataclass(kls)

# print(A.__fields__['o'].type_)
# print(fields(B)[0].type)

def get_pd(kls):
    for k, v in kls.__fields__.items():
        if is_acceptable_kls(v.type_):
            yield k
        
def get_dc(kls):
    for f in fields(kls):
        if is_acceptable_kls(f.type):
            yield f.name

# def get_dc(kls, name):
for x in get_dc(B):
    print(x)