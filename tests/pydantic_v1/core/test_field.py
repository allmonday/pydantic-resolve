# from __future__ import annotations
from pydantic import BaseModel
from pydantic_resolve.utils.class_util import get_class

def test_get_class():
    class Student(BaseModel):
        name: str = 'kikodo'

    stu = Student()
    stus = [Student(), Student()]

    assert get_class(stu) == Student
    assert get_class(stus) == Student
