import asyncio
from typing import List, Optional
from pydantic import BaseModel
from pydantic_resolve import Resolver, mapper, LoaderDepend

# loader functions
async def friends_batch_load_fn(names):
    mock_db = {
        'tangkikodo': ['tom', 'jerry'],
        'john': ['mike', 'wallace'],
        'trump': ['sam', 'jim'],
        'sally': ['sindy', 'lydia'],
    }
    result = []
    for name in names:
        friends = mock_db.get(name, [])
        result.append(friends)
    return result

async def contact_batch_load_fn(names):
    mock_db = {
        'tom': 100, 'jerry':200, 'mike': 3000, 'wallace': 400, 'sam': 500,
        'jim': 600, 'sindy': 700, 'lydia': 800, 'tangkikodo': 900, 'john': 1000,
        'trump': 1200, 'sally': 1300,
    }
    result = []
    for name in names:
        contact = mock_db.get(name, None)
        result.append(contact)
    return result

# schemas
class Contact(BaseModel):
    number: Optional[int]
class Friend(BaseModel):
    name: str

    contact: int = 0
    @mapper(lambda n: Contact(number=n))
    def resolve_contact(self, loader=LoaderDepend(contact_batch_load_fn)):
        return loader.load(self.name)
class User(BaseModel):
    name: str
    age: int

    greeting: str = ''
    def resolve_greeting(self):
        return f"hello, i'm {self.name}, {self.age} years old."

    contact: int = 0
    @mapper(lambda n: Contact(number=n))
    def resolve_contact(self, loader=LoaderDepend(contact_batch_load_fn)):
        return loader.load(self.name)
    
    friends: List[Friend] = []
    @mapper(lambda items: [Friend(name=item) for item in items])
    def resolve_friends(self, loader=LoaderDepend(friends_batch_load_fn)):
        return loader.load(self.name)

class Root(BaseModel):
    users: List[User] = []
    def resolve_users(self):
        return [
            User(name="tangkikodo", age=19), 
            User(name='john', age=21), 
            # User(name='trump', age=59), 
            # User(name='sally', age=21), 
            # User(name='some one', age=0)
        ]

async def main():
    import json
    root = Root()
    root = await Resolver().resolve(root)
    dct = root.dict()
    print(json.dumps(dct, indent=4))

asyncio.run(main())