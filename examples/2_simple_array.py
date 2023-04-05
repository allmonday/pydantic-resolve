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
    humans = [Human(name=f'man-{i}') for i in range(10)]
    results = await resolve(humans)
    print(results)

asyncio.run(main())