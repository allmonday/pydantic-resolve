from pydantic import BaseModel, Field
from dataclasses import dataclass
from typing import Annotated, get_type_hints

@dataclass
class LoaderInfo:
    by: str

def LoadBy(key):
    return LoaderInfo(by=key)

class User(BaseModel):
    age: Annotated[int, Field(ge=0, le=120, description="用户年龄"), LoadBy('user_id')] = 18

hints = get_type_hints(User)
age_hint = hints['age']
print("get_type_hints result:", age_hint)

raw_annotation = User.__annotations__['age']

if hasattr(raw_annotation, '__metadata__'):
    print("Annotated metadata from __annotations__:", raw_annotation.__metadata__)
else:
    print("Still not Annotated?")
