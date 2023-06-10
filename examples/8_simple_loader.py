import asyncio
from typing import List
from pydantic import BaseModel
from pydantic_resolve import Resolver
from aiodataloader import DataLoader

from pydantic_resolve.resolver import LoaderDepend

class FriendLoader(DataLoader):
    async def batch_load_fn(self, names):
        mock_db = {
            'tangkikodo': ['tom', 'jerry'],
            'john': ['mike', 'wallace'],
            'trump': ['sam', 'jim'],
            'sally': ['sindy', 'lydia'],
        }
        result = []
        for name in names:
            friends = mock_db.get(name, [])
            friends = [Friend(name=f) for f in friends]
            result.append(friends)
        return result

class Friend(BaseModel):
    name: str

class User(BaseModel):
    name: str
    age: int

    greeting: str = ''
    def resolve_greeting(self):
        return f"hello, i'm {self.name}, {self.age} years old."
    
    friends: List[Friend] = []
    def resolve_friends(self, loader=LoaderDepend(FriendLoader)):
        return loader.load(self.name)

async def main():
    users = [
        User(name="tangkikodo", age=19),
        User(name='john', age=21),
        User(name='trump', age=59),
        User(name='sally', age=21),
        User(name='some one', age=0),
    ]
    users = await Resolver().resolve(users)
    print(users)

asyncio.run(main())