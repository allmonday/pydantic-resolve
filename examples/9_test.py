import asyncio
from typing import List
from pydantic import BaseModel
from pydantic_resolve import Resolver

class SubUser(BaseModel):
    a1: str = 'a'
    b1: str = 'a'
    c1: str = 'a'
    d1: str = 'a'
    e1: str = 'a'
    f1: str = 'a'
    g1: str = 'a'
    h1: str = 'a'
    i1: str = 'a'
    j1: str = 'a'
    a: str = 'a'
    b: str = 'a'
    c: str = 'a'
    d: str = 'a'
    e: str = 'a'
    f: str = 'a'
    g: str = 'a'
    h: str = 'a'
    i: str = 'a'
    j: str = 'a'

class User(BaseModel):
    a1: str = 'a'
    b1: str = 'a'
    c1: str = 'a'
    d1: str = 'a'
    e1: str = 'a'
    f1: str = 'a'
    g1: str = 'a'
    h1: str = 'a'
    i1: str = 'a'
    j1: str = 'a'
    a: str = 'a'
    b: str = 'a'
    c: str = 'a'
    d: str = 'a'
    e: str = 'a'
    f: str = 'a'
    g: str = 'a'
    h: str = 'a'
    i: str = 'a'
    j: str = 'a'

    greeting: str = ''

    def resolve_greeting(self):
        return "hello world"

    subs: List[SubUser] = []

    def resolve_subs(self):
        return [SubUser() for _ in range(100)]

class UserGroup(BaseModel):
    users: List[User] = []

    def resolve_users(self):
        return [User() for _ in range(100)]
    
class SubUser2(BaseModel):
    a1: str = 'a'

class User2(BaseModel):
    a: str = 'a'

    greeting: str = ''

    def resolve_greeting(self):
        return "hello world"

    subs: List[SubUser2] = []

    def resolve_subs(self):
        return [SubUser2() for _ in range(100)]


class UserGroup2(BaseModel):
    users: List[User2] = []

    def resolve_users(self):
        return [User2() for _ in range(100)]


async def main(Kls):
    import time
    n = time.perf_counter()
    user = Kls()
    await Resolver().resolve(user)
    print(time.perf_counter() - n)

asyncio.run(main(UserGroup))
asyncio.run(main(UserGroup2))
# in pydantic-resolve:1.7.2 it takes 0.98 & 0.63
# in pydantic-resolve:1.8.0 it takes 0.27 & 0.20