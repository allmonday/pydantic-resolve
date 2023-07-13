import asyncio
from random import random
from pydantic import BaseModel
from pydantic_resolve import Resolver
from typing import List
import json

class Human(BaseModel):
    name: str
    lucky: bool = True
    async def resolve_lucky(self):
        print('calculating...')
        await asyncio.sleep(1)  # mock i/o
        return random() > 0.5
    
class Earth(BaseModel):
    humans: List[Human] = []
    def resolve_humans(self):
        return [dict(name=f'man-{i}') for i in range(10)]

async def main():
    earth = Earth()
    earth = await Resolver().resolve(earth)
    print(json.dumps(earth.dict(), indent=2))

asyncio.run(main())