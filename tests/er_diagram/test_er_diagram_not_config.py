import pytest
from typing import Optional, Annotated
from pydantic import BaseModel
from pydantic_resolve import config_resolver
from pydantic_resolve import LoadBy
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
        users = [
            dict(id=1, name="a"),
            dict(id=2, name="b"),
            dict(id=3, name="c"),
        ]
        user_map = { u['id']: u for u in users}
        return [user_map.get(k, None) for k in keys]


class BizCase1(Biz):
    user: Annotated[Optional[User], LoadBy('user_id')] = None
    
@pytest.mark.asyncio
async def test_resolver_factory_with_er_configs_inherit():
    with pytest.raises(ValueError):
        MyResolver = config_resolver('MyResolver', er_diagram=None)
        d = [BizCase1(id=1, name="qq", user_id=1), BizCase1(id=2, name="ww", user_id=2)]
        d = await MyResolver().resolve(d)