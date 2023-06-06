import asyncio
from pydantic import BaseModel
from pydantic_resolve import resolve

class Student(BaseModel):  # <==== can resolve fields
    name: str

    answer: str = ''
    async def resolve_answer(self) -> str:
        await asyncio.sleep(1)  # mock i/o
        return f'{self.name} say the answer is 42'

async def main():
    students = Student(name='john' )
    results = await resolve(students)
    print(results.json())

asyncio.run(main())