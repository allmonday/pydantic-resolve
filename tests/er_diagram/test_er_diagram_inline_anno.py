import pytest
from typing import Optional, Annotated, List
from pydantic import BaseModel
from pydantic_resolve import config_resolver
from pydantic_resolve import Relationship, DefineSubset, ensure_subset, base_entity
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
    __relationships__ = [
        Relationship(fk='user_id', name='user', target='User', loader=UserLoader),
        Relationship(fk='user_ids', name='users_a', target=list['User'], load_many=True, loader=UserLoader),
        Relationship(fk='user_ids_str',
                        name='users_b',
                        target=list['User'],
                        load_many=True,
                        load_many_fn=lambda x: [int(xx) for xx in x.split(',')] if x else [],
                        loader=UserLoader),
        Relationship(fk='id', name='foos', target=list['Foo'], loader=FooLoader),
        Relationship(fk='id', name='foos_in_str', target=list[str], loader=FooNameLoader),
        Relationship(fk='id', name='bars', target=list['Bar'], loader=BarLoader),
        Relationship(fk='id', name='special_bars', target=list['Bar'], loader=SpecialBarLoader),
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


# Get AutoLoad from the diagram
AutoLoad = BASE_ENTITY.get_diagram().create_auto_load()


class BizCase1(Biz):
    user: Annotated[Optional[User], AutoLoad()] = None
    foos: Annotated[List[Foo], AutoLoad()] = []
    foos_in_str: Annotated[List[str], AutoLoad()] = []
    bars: Annotated[List[Bar], AutoLoad()] = []
    special_bars: Annotated[list[Bar], AutoLoad()] = []
    users_a: Annotated[list[User], AutoLoad()] = []
    users_b: Annotated[list[User], AutoLoad()] = []
    

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
    user: Annotated[Optional[SubUser], AutoLoad()] = None

@pytest.mark.asyncio
async def test_resolver_factory_with_er_configs_inherit_2():
    MyResolver = config_resolver('MyResolver', er_diagram=BASE_ENTITY.get_diagram())
    d = BizCase2(id=1, name="qq", user_id=1)
    d = await MyResolver().resolve(d)
    assert d.user.id == 1


class BizCase3(DefineSubset):
    __pydantic_resolve_subset__ = (Biz, ['id', 'user_id'])

    user: Annotated[Optional[User], AutoLoad()] = None


@pytest.mark.asyncio
async def test_resolver_factory_with_er_configs_subset():
    MyResolver = config_resolver('MyResolver', er_diagram=BASE_ENTITY.get_diagram())
    d = BizCase3(id=1, user_id=1)
    d = await MyResolver().resolve(d)
    assert d.user is not None

@ensure_subset(Biz)
class BizCase5(BaseModel):
    id: int
    user_id: int

    user: Annotated[Optional[User], AutoLoad()] = None
    # foos_in_str_x: Annotated[List[str], AutoLoad()] = []


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
    for entity_cfg in diagram.entities:
        field_names = [rel.name for rel in entity_cfg.relationships]

        # Check for duplicates
        duplicates = [fn for fn in set(field_names) if field_names.count(fn) > 1]

        assert len(duplicates) == 0, (
            f"Entity {entity_cfg.kls.__name__} has duplicate field_name values: {duplicates}. "
            f"Each field_name must be unique within an entity."
        )


def test_field_name_matches_loadby_field():
    """Test that AutoLoad field names match the field_name in Relationship definitions."""
    diagram = BASE_ENTITY.get_diagram()

    # Get the Biz entity config
    biz_config = next(cfg for cfg in diagram.entities if cfg.kls.__name__ == 'Biz')

    # Extract field_names from relationships
    relationship_field_names = {rel.name for rel in biz_config.relationships}

    # Expected field names based on BizCase1 annotations
    expected_fields = {'user', 'users_a', 'users_b', 'foos', 'foos_in_str', 'bars', 'special_bars'}

    assert relationship_field_names == expected_fields, (
        f"Field names in relationships don't match AutoLoad annotations. "
        f"Expected: {expected_fields}, Got: {relationship_field_names}"
    )


# --- Tests for auto-added FK fields when DefineSubset omits them ---


class BizCaseOmitFk(DefineSubset):
    """Subset that omits owner FK field (user_id), relying on auto-add."""
    __subset__ = (Biz, ['id', 'name'])
    user: Annotated[Optional[User], AutoLoad()] = None


def test_autoload_fk_auto_added_when_omitted():
    """AutoLoad should auto-add the FK field with exclude=True when omitted from subset."""
    assert 'owner_id' not in ['id', 'name']  # not in explicit subset
    assert 'user_id' in BizCaseOmitFk.model_fields  # auto-added from relationship
    assert BizCaseOmitFk.model_fields['user_id'].exclude is True


def test_autoload_fk_not_duplicated_when_explicitly_included():
    """If FK is already in subset, it should not be re-added."""
    assert 'user_id' in BizCase3.model_fields
    # owner_id field from Biz is user_id — check it's the original, not auto-added
    # BizCase3 explicitly includes user_id in its subset tuple
    assert BizCase3.model_fields['user_id'].exclude is not True


def test_autoload_omitted_fk_excluded_from_dump():
    """Auto-added FK fields should be excluded from model_dump()."""
    obj = BizCaseOmitFk(id=1, name='test', user_id=2)
    dumped = obj.model_dump()
    assert 'user_id' not in dumped
    assert dumped == {'id': 1, 'name': 'test', 'user': None}


@pytest.mark.asyncio
async def test_autoload_omitted_fk_resolves_correctly():
    """Full integration: subset with auto-added FK resolves via AutoLoad."""
    MyResolver = config_resolver('MyResolver', er_diagram=BASE_ENTITY.get_diagram())
    d = BizCaseOmitFk(id=1, name='test', user_id=1)
    d = await MyResolver().resolve(d)
    assert d.user is not None
    assert d.user.name == 'a'
    # user_id still excluded from dump
    assert 'user_id' not in d.model_dump()
