from __future__ import annotations
from pydantic import BaseModel
from pydantic_resolve import Resolver, MissingAnnotationError
import pytest

class Student(BaseModel):
    name: str
    intro: str = ''
    def resolve_intro(self):
        return f'hello {self.name}'

@pytest.mark.asyncio
async def test_check_miss_anno():
    stu = Student(name="martin")
    with pytest.raises(MissingAnnotationError):
        await Resolver(ensure_type=True).resolve(stu)
