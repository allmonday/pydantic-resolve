import asyncio
from pydantic import BaseModel
from pydantic_resolve import resolve

class Book(BaseModel):
    name: str

class Student(BaseModel):
    name: str
    greet: str = ''
    async def resolve_greet(self):
        await asyncio.sleep(1)  # mock i/o
        return f'hello {self.name}'

async def main():
    students = [Student(name='john' )]
    results = await resolve(students)
    print(results)

asyncio.run(main())

# output: [Student(name='john', greet='hello john')]