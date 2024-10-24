from __future__ import annotations
from typing import List, Optional
import asyncio
from pydantic import BaseModel
from pydantic_resolve import Resolver
import pytest

async def set_after(fut, value):
    await asyncio.sleep(1)
    fut.set_result(value)

class Student(BaseModel):
    scores: List[int] = []
    async def resolve_scores(self) -> List[int]:
        return [1,2,3]

    age: Optional[int] = None
    def resolve_age(self) -> Optional[int]:
        return 12

    name: Optional[str] = None
    def resolve_name(self) -> Optional[str]:
        return 'name'
    
    future: Optional[str] = None
    def resolve_future(self) -> Optional[str]:
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        loop.create_task(set_after(fut, 'hello'))
        return fut

@pytest.mark.asyncio
async def test_resolve_future():
    stu = Student()
    result = await Resolver().resolve(stu)
    expected = {
        'name': 'name',
        'scores': [1,2,3],
        'age': 12,
        'future': 'hello'
    }
    assert result.model_dump() == expected
