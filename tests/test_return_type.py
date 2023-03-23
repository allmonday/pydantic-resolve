from __future__ import annotations
from typing import Tuple, Optional
import unittest
import asyncio
from pydantic import BaseModel
from pydantic_resolve import resolve


class TestReturnType(unittest.IsolatedAsyncioTestCase):

    async def test_resolver_1(self):
        async def get_scores():
            await asyncio.sleep(1)
            return [1,2,3]

        async def set_after(fut, value):
            await asyncio.sleep(1)
            fut.set_result(value)

        class Student(BaseModel):
            name: str
            
            scores: Tuple[int, ...] = tuple()
            async def resolve_scores(self):
                return await get_scores()

            age: Optional[int] = None
            def resolve_age(self):
                return 12
            
            future: Optional[str] = None
            def resolve_future(self):
                loop = asyncio.get_running_loop()
                fut = loop.create_future()
                loop.create_task(set_after(fut, 'hello'))
                return fut

        stu = Student(name="cathy")
        result = await resolve(stu)
        expected = {
            'name': 'cathy',
            'scores': [1,2,3],
            'age': 12,
            'future': 'hello'
        }
        self.assertEqual(result.dict(), expected)
