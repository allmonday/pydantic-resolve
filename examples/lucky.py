import asyncio
from random import random
from pydantic import BaseModel
from pydantic_resolve import resolve

class Human(BaseModel):
    name: str
    lucky: bool = True

    async def resolve_lucky(self):
        print('calculating...')
        await asyncio.sleep(1)  # mock i/o
        return random() > 0.5

async def main():
    students = Human(name='john' )
    results = await resolve(students)
    print(results.json())

asyncio.run(main())