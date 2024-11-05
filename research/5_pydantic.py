from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel
from pydantic_resolve.utils.class_util import update_forward_refs

class ClassRoom(BaseModel):
    students: List[Student]

class Student(BaseModel):
    id: int
    name: str
    books: List[Book]

class Book(BaseModel):
    name: str


ClassRoom.update_forward_refs()
Student.update_forward_refs()

update_forward_refs(ClassRoom)


print('------------')

print(ClassRoom.__fields__['students'].annotation)
print(ClassRoom.__fields__['students'].type_)
print(ClassRoom.__fields__['students'].outer_type_)

print('------------')

print(Student.__fields__['books'].annotation)
print(Student.__fields__['books'].type_)
print(Student.__fields__['books'].outer_type_)