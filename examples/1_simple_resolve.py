import asyncio
from typing import List
from pydantic import BaseModel
from pydantic_resolve import Resolver
import json

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
        return [dict(name="tom"), dict(name="jerry")]

async def main():
    user = User(name="tangkikodo", age=19)
    user = await Resolver().resolve(user)
    print(json.dumps(user.dict(), indent=2))

asyncio.run(main())