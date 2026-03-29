import pytest
import logging
from typing import Optional, Annotated
from pydantic import BaseModel
from pydantic_resolve import (
    config_resolver,
    Entity,
    Relationship,
    LoadBy,
    DefineSubset,
    ErDiagram,
    ensure_subset,
    Loader
)
from aiodataloader import DataLoader


class Biz(BaseModel):
    id: int
    name: str
    user_id: int
    user_id_str: str
    user_ids: list[int] = []
    user_ids_str:str = ''

class Foo(BaseModel):
    id: int
    name: str
    biz_id: int

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

class SpecialBarLoader(DataLoader):
    async def batch_load_fn(self, keys):
        bars = [
            dict(id=1, name="special-bar1", biz_id=1),
            dict(id=2, name="special-bar2", biz_id=1),
            dict(id=3, name="special-bar3", biz_id=2),
        ]
        bar_map = {}
        for b in bars:
            bar_map.setdefault(b['biz_id'], []).append(b)
        return [bar_map.get(k, []) for k in keys]

class FooLoader(DataLoader):
    async def batch_load_fn(self, keys):
        foos = [
            dict(id=1, name="foo1", biz_id=1),
            dict(id=2, name="foo2", biz_id=1),
            dict(id=3, name="foo3", biz_id=2),
        ]
        foo_map = {}
        for f in foos:
            foo_map.setdefault(f['biz_id'], []).append(f)
        return [foo_map.get(k, []) for k in keys]

class FooNameLoader(DataLoader):
    async def batch_load_fn(self, keys):
        foos = [
            dict(id=1, name="foo1", biz_id=1),
            dict(id=2, name="foo2", biz_id=1),
            dict(id=3, name="foo3", biz_id=2),
        ]
        foo_map = {}
        for f in foos:
            foo_map.setdefault(f['biz_id'], []).append(f)
        val = [foo_map.get(k, []) for k in keys]
        return [[vv['name'] for vv in v] for v in val]


diagram = ErDiagram(
    configs=[
        Entity(kls=Biz, relationships=[
            Relationship(field='user_id', field_name='user', target_kls=User, loader=UserLoader),
            Relationship(field='user_id_str', field_name='user_2', field_fn=int, target_kls=User, loader=UserLoader),
            Relationship(field='user_ids', field_name='users_a', target_kls=list[User], load_many=True, loader=UserLoader),
            Relationship(field='user_ids_str',
                         field_name='users_b',
                         target_kls=list[User],
                         load_many=True,
                         load_many_fn=lambda x: [int(xx) for xx in x.split(',')] if x else [],
                         loader=UserLoader),
            # MultipleRelationship feature removed
            # Relationship(field='id', field_name='foos', target_kls=list[Foo], loader=FooLoader),
            # Relationship(field='id', field_name='bars', target_kls=list[Bar], loader=BarLoader),
        ])
    ]
)

class BizCase0(Biz):
    user: Annotated[Optional[User], LoadBy()] = None
    def resolve_user(self, loader=Loader(UserLoader)):
        return loader.load(self.user_id)


@pytest.mark.asyncio
async def test_resolver_factory_warning(caplog):
    MyResolver = config_resolver('MyResolver', er_diagram=diagram)
    d = [BizCase0(id=1, name="qq", user_id=1, user_id_str='1', user_ids=[1], user_ids_str='1,2'), BizCase0(id=2, name="ww", user_id=2, user_id_str='2')]
    with caplog.at_level(logging.WARNING, logger="pydantic_resolve.utils.er_diagram"):
        await MyResolver().resolve(d)
    assert any('resolve_user already exists' in record.message for record in caplog.records)

class BizCase1(Biz):
    user: Annotated[Optional[User], LoadBy()] = None
    user_2: Annotated[Optional[User], LoadBy()] = None
    # user_3: Annotated[User | None, LoadBy()] = None  # Removed - no corresponding relationship
    # foos: Annotated[List[Foo], LoadBy()] = []  # MultipleRelationship removed
    # foos_in_str: Annotated[List[str], LoadBy()] = []  # MultipleRelationship removed
    # bars: Annotated[List[Bar], LoadBy()] = []  # MultipleRelationship removed
    # special_bars: Annotated[list[Bar], LoadBy()] = []  # MultipleRelationship removed
    users_a: Annotated[list[User], LoadBy()] = []
    users_b: Annotated[list[User], LoadBy()] = []
    

@pytest.mark.asyncio
async def test_resolver_factory_with_er_configs_inherit():
    MyResolver = config_resolver('MyResolver', er_diagram=diagram)
    d = [BizCase1(id=1, name="qq", user_id=1, user_id_str='1', user_ids=[1], user_ids_str='1,2'), BizCase1(id=2, name="ww", user_id=2, user_id_str='2')]
    d = await MyResolver().resolve(d)

    assert d[0].user.name == "a"
    assert d[0].user_2.name == "a"
    # assert d[0].user_3.name == "a"  # Removed - no corresponding relationship
    # MultipleRelationship feature removed - commented out assertions
    # assert d[0].bars == [Bar(id=1, name="bar1", biz_id=1), Bar(id=2, name="bar2", biz_id=1)]
    # assert d[0].special_bars == [Bar(id=1, name="special-bar1", biz_id=1), Bar(id=2, name="special-bar2", biz_id=1)]
    assert d[0].users_a == [User(id=1, name="a")]
    assert d[0].users_b == [User(id=1, name="a"), User(id=2, name="b")]
    # assert d[0].foos_in_str == ["foo1", "foo2"]

    assert d[1].user.name == "b"
    assert d[1].user_2.name == "b"
    # assert d[1].user_3.name == "b"  # Removed - no corresponding relationship
    # assert d[1].foos == [Foo(id=3, name="foo3", biz_id=2)]
    assert d[1].users_a == []
    assert d[1].users_b == []


class SubUser(DefineSubset):
    __pydantic_resolve_subset__ = (User, ['id'])

class BizCase2(Biz):
    user: Annotated[Optional[SubUser], LoadBy()] = None

@pytest.mark.asyncio
async def test_resolver_factory_with_er_configs_inherit_2():
    MyResolver = config_resolver('MyResolver', er_diagram=diagram)
    d = BizCase2(id=1, name="qq", user_id=1, user_id_str='1')
    d = await MyResolver().resolve(d)
    assert d.user.id == 1


class BizCase3(DefineSubset):
    __pydantic_resolve_subset__ = (Biz, ['id', 'user_id'])

    user: Annotated[Optional[User], LoadBy()] = None


@pytest.mark.asyncio
async def test_resolver_factory_with_er_configs_subset():
    MyResolver = config_resolver('MyResolver', er_diagram=diagram)
    d = BizCase3(id=1, user_id=1)
    d = await MyResolver().resolve(d)
    assert d.user is not None

@ensure_subset(Biz)
class BizCase5(BaseModel):
    id: int
    user_id: int

    user: Annotated[Optional[User], LoadBy()] = None
    # foos_in_str_x: Annotated[List[str], LoadBy('id', biz='foo_name')] = []


@pytest.mark.asyncio
async def test_resolver_factory_with_permitive_annotation():
    MyResolver = config_resolver('MyResolver', er_diagram=diagram)
    d = BizCase5(id=1, user_id=1)
    d = await MyResolver().resolve(d)
    assert d.user is not None
    # assert d.foos_in_str_x == ["foo1", "foo2"]


@pytest.mark.asyncio
async def test_loadby_references_nonexistent_field():
    """Test that LoadBy referencing a non-existent field raises ValueError when resolver is used."""
    # With the new LoadBy() API, validation is deferred until resolver time
    # when there's no global ER diagram configured at class definition time.
    class BizCase6(DefineSubset):
        __pydantic_resolve_subset__ = (Biz, ['id', 'user_id'])

        # This field name 'user_xyz' doesn't match any relationship field_name
        user_xyz: Annotated[Optional[User], LoadBy()] = None

    # Class definition succeeds (validation deferred)
    # But when we try to use it with a resolver, it should fail
    MyResolver = config_resolver('MyResolver', er_diagram=diagram)
    with pytest.raises(AttributeError, match='Relationship with field_name "user_xyz" not found'):
        d = BizCase6(id=1, user_id=1)
        await MyResolver().resolve(d)