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

print(dir(str))
print(dir(B))