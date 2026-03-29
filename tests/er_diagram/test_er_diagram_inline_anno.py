import pytest
from typing import Optional, Annotated, List
from pydantic import BaseModel
from pydantic_resolve import config_resolver
from pydantic_resolve import Relationship, LoadBy, DefineSubset, ensure_subset, base_entity
from aiodataloader import DataLoader


BASE_ENTITY = base_entity()


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


class Biz(BaseModel, BASE_ENTITY):
    __pydantic_resolve_relationships__ = [
        Relationship(field='user_id', field_name='user', target_kls='User', loader=UserLoader),
        Relationship(field='user_ids', field_name='users_a', target_kls=list['User'], load_many=True, loader=UserLoader),
        Relationship(field='user_ids_str',
                        field_name='users_b',
                        target_kls=list['User'],
                        load_many=True,
                        load_many_fn=lambda x: [int(xx) for xx in x.split(',')] if x else [],
                        loader=UserLoader),
        Relationship(field='id', field_name='foos', target_kls=list['Foo'], loader=FooLoader),
        Relationship(field='id', field_name='foos_in_str', target_kls=list[str], loader=FooNameLoader),
        Relationship(field='id', field_name='bars', target_kls=list['Bar'], loader=BarLoader),
        Relationship(field='id', field_name='special_bars', target_kls=list['Bar'], loader=SpecialBarLoader),
    ]

    id: int
    name: str
    user_id: int
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



class BizCase1(Biz):
    user: Annotated[Optional[User], LoadBy()] = None
    foos: Annotated[List[Foo], LoadBy()] = []
    foos_in_str: Annotated[List[str], LoadBy()] = []
    bars: Annotated[List[Bar], LoadBy()] = []
    special_bars: Annotated[list[Bar], LoadBy()] = []
    users_a: Annotated[list[User], LoadBy()] = []
    users_b: Annotated[list[User], LoadBy()] = []
    

@pytest.mark.asyncio
async def test_resolver_factory_with_er_configs_inherit():
    MyResolver = config_resolver('MyResolver', er_diagram=BASE_ENTITY.get_diagram())
    d = [BizCase1(id=1, name="qq", user_id=1, user_ids=[1], user_ids_str='1,2'), BizCase1(id=2, name="ww", user_id=2)]
    d = await MyResolver().resolve(d)

    assert d[0].user.name == "a"
    assert d[0].bars == [Bar(id=1, name="bar1", biz_id=1), Bar(id=2, name="bar2", biz_id=1)]
    assert d[0].special_bars == [Bar(id=1, name="special-bar1", biz_id=1), Bar(id=2, name="special-bar2", biz_id=1)]
    assert d[0].users_a == [User(id=1, name="a")]
    assert d[0].users_b == [User(id=1, name="a"), User(id=2, name="b")]
    assert d[0].foos_in_str == ["foo1", "foo2"]

    assert d[1].user.name == "b"
    assert d[1].foos == [Foo(id=3, name="foo3", biz_id=2)]
    assert d[1].users_a == []
    assert d[1].users_b == []

    

class SubUser(DefineSubset):
    __pydantic_resolve_subset__ = (User, ['id'])

class BizCase2(Biz):
    user: Annotated[Optional[SubUser], LoadBy()] = None

@pytest.mark.asyncio
async def test_resolver_factory_with_er_configs_inherit_2():
    MyResolver = config_resolver('MyResolver', er_diagram=BASE_ENTITY.get_diagram())
    d = BizCase2(id=1, name="qq", user_id=1)
    d = await MyResolver().resolve(d)
    assert d.user.id == 1


class BizCase3(DefineSubset):
    __pydantic_resolve_subset__ = (Biz, ['id', 'user_id'])

    user: Annotated[Optional[User], LoadBy()] = None


@pytest.mark.asyncio
async def test_resolver_factory_with_er_configs_subset():
    MyResolver = config_resolver('MyResolver', er_diagram=BASE_ENTITY.get_diagram())
    d = BizCase3(id=1, user_id=1)
    d = await MyResolver().resolve(d)
    assert d.user is not None

@pytest.mark.asyncio
async def test_resolver_factory_of_er_config_auto_add_fk_field():
    """Test that missing LoadBy FK fields are auto-added with exclude=True."""
    from pydantic_resolve import config_global_resolver
    config_global_resolver(er_diagram=BASE_ENTITY.get_diagram())

    class BizCase4(DefineSubset):
        __pydantic_resolve_subset__ = (Biz, ['id'], ['user'])

        user: Annotated[Optional[User], LoadBy()] = None

    MyResolver = config_resolver('MyResolver', er_diagram=BASE_ENTITY.get_diagram())

    # user_id is not in subset but should be auto-added
    d = BizCase4(id=1, user_id=1)

    # Verify user_id field exists and has correct value
    assert hasattr(d, 'user_id')
    assert d.user_id == 1

    # Verify user_id is excluded from serialization
    dumped = d.model_dump()
    assert 'user_id' not in dumped
    assert dumped == {'id': 1, 'user': None}

    # Resolve should work correctly
    d = await MyResolver().resolve(d)
    assert d.user is not None
    assert d.user.name == "a"

    # After resolve, user_id should still be excluded
    dumped = d.model_dump()
    assert 'user_id' not in dumped
    assert 'user' in dumped

@ensure_subset(Biz)
class BizCase5(BaseModel):
    id: int
    user_id: int

    user: Annotated[Optional[User], LoadBy()] = None
    # foos_in_str_x: Annotated[List[str], LoadBy()] = []


@pytest.mark.asyncio
async def test_resolver_factory_with_permitive_annotation():
    MyResolver = config_resolver('MyResolver', er_diagram=BASE_ENTITY.get_diagram())
    d = BizCase5(id=1, user_id=1)
    d = await MyResolver().resolve(d)
    assert d.user is not None
    # assert d.foos_in_str_x == ["foo1", "foo2"]


def test_validate_unique_field_name_in_relationships():
    """Test that field_name is unique across all relationships in an entity config."""
    diagram = BASE_ENTITY.get_diagram()

    # Check each entity config for unique field_name
    for entity_cfg in diagram.configs:
        field_names = [rel.field_name for rel in entity_cfg.relationships]

        # Check for duplicates
        duplicates = [fn for fn in set(field_names) if field_names.count(fn) > 1]

        assert len(duplicates) == 0, (
            f"Entity {entity_cfg.kls.__name__} has duplicate field_name values: {duplicates}. "
            f"Each field_name must be unique within an entity."
        )


def test_field_name_matches_loadby_field():
    """Test that LoadBy field names match the field_name in Relationship definitions."""
    diagram = BASE_ENTITY.get_diagram()

    # Get the Biz entity config
    biz_config = next(cfg for cfg in diagram.configs if cfg.kls.__name__ == 'Biz')

    # Extract field_names from relationships
    relationship_field_names = {rel.field_name for rel in biz_config.relationships}

    # Expected field names based on BizCase1 annotations
    expected_fields = {'user', 'users_a', 'users_b', 'foos', 'foos_in_str', 'bars', 'special_bars'}

    assert relationship_field_names == expected_fields, (
        f"Field names in relationships don't match LoadBy annotations. "
        f"Expected: {expected_fields}, Got: {relationship_field_names}"
    )
