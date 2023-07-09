import asyncio
from typing import List, Optional
from pydantic import BaseModel
from pydantic_resolve import Resolver, mapper, LoaderDepend

# define loader functions
async def friends_batch_load_fn(names):
    mock_db = {
        'tangkikodo': ['tom', 'jerry'],
        'john': ['mike', 'wallace'],
        'trump': ['sam', 'jim'],
        'sally': ['sindy', 'lydia'],
    }
    return [mock_db.get(name, []) for name in names]

async def contact_batch_load_fn(names):
    mock_db = {
        'tom': 1001, 'jerry': 1002, 'mike': 1003, 'wallace': 1004, 'sam': 1005,
        'jim': 1006, 'sindy': 1007, 'lydia': 1008, 'tangkikodo': 1009, 'john': 1010,
        'trump': 2011, 'sally': 2012,
    }
    result = []
    for name in names:
        n = mock_db.get(name, None)
        result.append({'number': n} if n else None)  # conver to auto mapping compatible style
    return result

# define schemas
class Contact(BaseModel):
    number: Optional[int]
    

class Friend(BaseModel):
    name: str

    contact: Optional[Contact] = None
    def resolve_contact(self, contact_loader=LoaderDepend(contact_batch_load_fn)):
        return contact_loader.load(self.name)
    
    is_contact_10: bool = False  # starts with 10
    def post_is_contact_10(self):
        if self.contact:
            if str(self.contact.number).startswith('10'):
                self.is_contact_10 = True
        else:
            self.is_contact_10 = False


class User(BaseModel):
    name: str
    age: int

    greeting: str = ''
    async def resolve_greeting(self):
        await asyncio.sleep(1)
        return f"hello, i'm {self.name}, {self.age} years old."

    contact: Optional[Contact] = None
    def resolve_contact(self, contact_loader=LoaderDepend(contact_batch_load_fn)):
        return contact_loader.load(self.name)
    
    friends: List[Friend] = []
    @mapper(lambda names: [Friend(name=name) for name in names])
    def resolve_friends(self, friend_loader=LoaderDepend(friends_batch_load_fn)):
        return friend_loader.load(self.name)
    
    friend_count: int = 0
    def post_friend_count(self):
        self.friend_count = len(self.friends)

class Root(BaseModel):
    users: List[User] = []
    def resolve_users(self):
        return [
            {"name": "tangkikodo", "age": 19},
            {"name": "john", "age": 20},
            {"name": "trump", "age": 21},
            {"name": "sally", "age": 22},
            {"name": "no man", "age": 23},
        ]

async def main():
    import json
    root = Root()
    root = await Resolver().resolve(root)
    dct = root.dict()
    print(json.dumps(dct, indent=4))

asyncio.run(main())