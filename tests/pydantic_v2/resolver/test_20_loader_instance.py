from typing import List
from pydantic import BaseModel
from pydantic_resolve import Resolver, mapper, LoaderDepend
from aiodataloader import DataLoader
import pytest

counter = {
    "n": 0
}

# define loader functions
class FriendLoader(DataLoader):
    async def batch_load_fn(self, names):
        print(names)
        counter["n"] += 1
        mock_db = {
            'tangkikodo': ['tom', 'jerry'],
            'john': ['mike', 'wallace'],
            'trump': ['sam', 'jim'],
            'sally': ['sindy', 'lydia'],
        }
        return [mock_db.get(name, []) for name in names]

class FriendLoaderCopy(DataLoader):
    async def batch_load_fn(self, names):
        print(names)
        counter["n"] += 1
        mock_db = {
            'tangkikodo': ['tom', 'jerry'],
            'john': ['mike', 'wallace'],
            'trump': ['sam', 'jim'],
            'sally': ['sindy', 'lydia'],
        }
        return [mock_db.get(name, []) for name in names]

class Friend(BaseModel):
    name: str

class User(BaseModel):
    name: str
    age: int

    friends: List[Friend] = []
    @mapper(lambda names: [Friend(name=name) for name in names])
    def resolve_friends(self, friend_loader=LoaderDepend(FriendLoader)):
        return friend_loader.load(self.name)

class Root(BaseModel):
    users: List[User] = []
    @mapper(lambda items: [User(**item) for item in items])
    def resolve_users(self):
        return [
            {"name": "tangkikodo", "age": 19}, 
            {"name": "john", "age": 19}, 
        ]

@pytest.mark.asyncio
async def test_loader_instance_0():
    counter["n"] = 0
    root = Root()
    loader = FriendLoader()
    loader.prime('tangkikodo', ['tom', 'jerry'])
    loader.prime('john', ['mike', 'wallace'])
    result = await Resolver(loader_instances={FriendLoader: loader}).resolve(root)
    assert len(result.users[0].friends) == 2
    assert counter["n"] == 0

@pytest.mark.asyncio
async def test_loader_instance_1():
    counter["n"] = 0
    root = Root()
    loader = FriendLoader()
    await loader.load_many(['tangkikodo', 'john'])
    result = await Resolver(loader_instances={FriendLoader: loader}).resolve(root)
    assert len(result.users[0].friends) == 2
    assert counter["n"] == 1

@pytest.mark.asyncio
async def test_loader_instance_2():
    counter["n"] = 0
    root = Root()
    loader = FriendLoader()
    await loader.load_many(['tangkikodo'])
    result = await Resolver(loader_instances={FriendLoader: loader}).resolve(root)
    assert len(result.users[0].friends) == 2
    assert counter["n"] == 2

@pytest.mark.asyncio
async def test_loader_instance_3():
    root = Root()
    loader = FriendLoader()
    await loader.load_many(['tangkikodo'])
    with pytest.raises(AttributeError):
        await Resolver(loader_instances={FriendLoaderCopy: loader}).resolve(root)

@pytest.mark.asyncio
async def test_loader_instance_4():
    root = Root()
    loader = FriendLoader()
    await loader.load_many(['tangkikodo'])
    class A:
        name= 'a'

    with pytest.raises(AttributeError):
        await Resolver(loader_instances={A: loader}).resolve(root)