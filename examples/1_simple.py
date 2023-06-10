import asyncio
from typing import List
from pydantic import BaseModel
from pydantic_resolve import resolve

class Student(BaseModel):  # <==== can resolve fields
    name: str

    answer: str = ''
    async def resolve_answer(self) -> str:
        await asyncio.sleep(1)  # mock i/o
        return f'{self.name} say the answer is 42'

class Friend(BaseModel):
    name: str

class User(BaseModel):
    name: str
    age: int

    greeting: str = ''
    def resolve_greeting(self):
        return f"hello, i'm {self.name}, {self.age} years old."
    
    friends: List[Friend] = []

    async def resolve_friends(self):
        await asyncio.sleep(1)
        return [Friend(name="tom"), Friend(name="jerry")]

async def main():
    students = Student(name='john' )
    students = await resolve(students)
    print(students.json())

    user = User(name="tangkikodo", age=19)
    user = await resolve(user)
    print(user.json())

asyncio.run(main())