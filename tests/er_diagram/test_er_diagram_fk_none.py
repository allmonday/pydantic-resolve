import pytest
from typing import Optional, Annotated
from pydantic import BaseModel
from pydantic_resolve import config_resolver
from pydantic_resolve import ErConfig, Relationship, LoadBy, ErDiagram
from aiodataloader import DataLoader


class Biz(BaseModel):
    id: Optional[int]
    name: str
    user_id: Optional[int]

class Bar(BaseModel):
    id: int
    name: str
    biz_id: int

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

class BarLoader(DataLoader):
    async def batch_load_fn(self, keys):
        bars = [
            dict(id=1, name="bar1", biz_id=1),
            dict(id=2, name="bar2", biz_id=1),
            dict(id=3, name="bar3", biz_id=2),
        ]
        bar_map = {}
        for b in bars:
            bar_map.setdefault(b['biz_id'], []).append(b)
        return [bar_map.get(k, []) for k in keys]

diagram = ErDiagram(
    configs=[
        ErConfig(kls=Biz, relationships=[
            Relationship(field='user_id', target_kls=User, loader=UserLoader),
            Relationship(field='id', target_kls=list[Bar], field_none_default_factory=list, loader=BarLoader),
        ])
    ]
)

class BizCase1(Biz):
    user: Annotated[Optional[User], LoadBy('user_id')] = None
    bars: Annotated[list[Bar], LoadBy('id')] = []
    

@pytest.mark.asyncio
async def test_resolver_factory_with_er_configs_inherit():
    MyResolver = config_resolver('MyResolver', er_diagram=diagram)
    d = [BizCase1(id=None, name="qq", user_id=None)]
    d = await MyResolver().resolve(d)

    assert d[0].user is None
    assert d[0].bars == []