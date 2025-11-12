import pytest
from typing import Optional, Annotated
from pydantic import BaseModel
from pydantic_resolve.utils.resolver_factory import config_resolver
from pydantic_resolve import ErConfig, Relationship, LoadBy, DefineSubset
from aiodataloader import DataLoader


class Biz(BaseModel):
    id: int
    name: str
    user_id: int

class User(BaseModel):
    id: int
    name: str

class UserLoader(DataLoader):
    async def batch_load_fn(self, keys):
        print(keys)
        users = [
            dict(id=1, name="a"),
            dict(id=2, name="b"),
            dict(id=3, name="c"),
        ]
        user_map = { u['id']: u for u in users}
        return [user_map.get(k, None) for k in keys]

configs = [
    ErConfig(kls=Biz, relationships=[
        Relationship(field='user_id', target_kls=User, loader=UserLoader)
    ])
]

class BizCase1(Biz):
    user: Annotated[Optional[User], LoadBy('user_id')] = None
    

@pytest.mark.asyncio
async def test_resolver_factory_with_er_configs_inherit():
    MyResolver = config_resolver('MyResolver', er_configs=configs)
    d = BizCase1(id=1, name="qq", user_id=1)
    d = await MyResolver().resolve(d)
    assert d.user.name == "a"

class SubUser(DefineSubset):
    __pydantic_resolve_subset__ = (User, ['id'])

class BizCase2(Biz):
    user: Annotated[Optional[SubUser], LoadBy('user_id')] = None

@pytest.mark.asyncio
async def test_resolver_factory_with_er_configs_inherit_2():
    MyResolver = config_resolver('MyResolver', er_configs=configs)
    d = BizCase2(id=1, name="qq", user_id=1)
    d = await MyResolver().resolve(d)
    assert d.user.id == 1


class BizCase3(DefineSubset):
    __pydantic_resolve_subset__ = (Biz, ['id', 'user_id'])
    user: Annotated[Optional[User], LoadBy('user_id')] = None


@pytest.mark.asyncio
async def test_resolver_factory_with_er_configs_subset():
    MyResolver = config_resolver('MyResolver', er_configs=configs)
    d = BizCase3(id=1, user_id=1)
    d = await MyResolver().resolve(d)
    assert d.user is not None

class BizCase4(BaseModel):
    user: Annotated[Optional[User], LoadBy('user_id')] = None

@pytest.mark.asyncio
async def test_resolver_factory_of_er_config_not_found():
    MyResolver = config_resolver('MyResolver', er_configs=configs)
    d = BizCase4(id=1, user_id=1)
    with pytest.raises(AttributeError):
        await MyResolver().resolve(d)
