"""Tests for implicit AutoLoad — fields matching relationship names
are auto-resolved without needing Annotated[..., AutoLoad()] annotation."""
import pytest
import logging
from typing import Optional, Annotated
from pydantic import BaseModel
from pydantic_resolve import (
    config_resolver,
    Relationship,
    ErDiagram,
    DefineSubset,
    base_entity,
    Loader,
)
from pydantic_resolve import AutoLoad
from aiodataloader import DataLoader


class User(BaseModel):
    id: int
    name: str


class UserLoader(DataLoader):
    async def batch_load_fn(self, keys):
        users = {1: User(id=1, name="alice"), 2: User(id=2, name="bob")}
        return [users.get(k) for k in keys]


class TaskLoader(DataLoader):
    async def batch_load_fn(self, keys):
        # keys are sprint_ids, return tasks grouped by owner_id (as sprint_id for test)
        tasks_data = [
            dict(id=1, title="task1", owner_id=1),
            dict(id=2, title="task2", owner_id=2),
            dict(id=3, title="task3", owner_id=1),
        ]
        task_map: dict[int, list[dict]] = {}
        for t in tasks_data:
            task_map.setdefault(1, []).append(t)  # all tasks belong to sprint 1
        return [task_map.get(k, []) for k in keys]


BASE_ENTITY = base_entity()


class Task(BaseModel, BASE_ENTITY):
    __relationships__ = [
        Relationship(fk='owner_id', name='owner', target=User, loader=UserLoader),
    ]
    id: int
    title: str
    owner_id: int


class Sprint(BaseModel, BASE_ENTITY):
    __relationships__ = [
        Relationship(fk='id', name='tasks', target=list[Task], loader=TaskLoader),
    ]
    id: int
    name: str


diagram = BASE_ENTITY.get_diagram()


# === Test 1: Basic implicit matching ===

class TaskView(Task):
    owner: Optional[User] = None  # implicit: matches relationship 'owner'


@pytest.mark.asyncio
async def test_implicit_basic():
    """Field name matches relationship name, no annotation needed."""
    MyResolver = config_resolver('TestResolver1', er_diagram=diagram)
    data = TaskView(id=1, title="task1", owner_id=1)
    result = await MyResolver().resolve(data)
    assert result.owner is not None
    assert result.owner.name == "alice"


# === Test 2: Nested implicit (Sprint -> tasks -> owner) ===

class TaskViewNested(Task):
    owner: Optional[User] = None  # implicit


class SprintView(Sprint):
    tasks: list[TaskViewNested] = []  # implicit: matches relationship 'tasks'


@pytest.mark.asyncio
async def test_implicit_nested():
    """Two-level implicit: Sprint.tasks + Task.owner."""
    MyResolver = config_resolver('TestResolver2', er_diagram=diagram)
    data = SprintView(id=1, name="sprint1")
    result = await MyResolver().resolve(data)
    assert len(result.tasks) == 3
    assert result.tasks[0].owner.name == "alice"
    assert result.tasks[1].owner.name == "bob"


# === Test 3: DefineSubset implicit matching ===

class TaskSummary(DefineSubset):
    __pydantic_resolve_subset__ = (Task, ['id', 'title', 'owner_id'])

    owner: Optional[User] = None  # implicit, no AutoLoad() annotation


@pytest.mark.asyncio
async def test_implicit_subset():
    """DefineSubset with implicit matching (no AutoLoad annotation)."""
    MyResolver = config_resolver('TestResolver3', er_diagram=diagram)
    data = TaskSummary(id=1, title="task1", owner_id=1)
    result = await MyResolver().resolve(data)
    assert result.owner is not None
    assert result.owner.name == "alice"


# === Test 4: DefineSubset FK auto-add (omitted FK field) ===

class TaskCard(DefineSubset):
    __pydantic_resolve_subset__ = (Task, ['id', 'title'])
    # owner_id is NOT selected, but should be auto-added by implicit matching

    owner: Optional[User] = None  # implicit, FK auto-added


@pytest.mark.asyncio
async def test_implicit_subset_fk_auto_add():
    """FK field auto-added even in implicit subset scenario."""
    MyResolver = config_resolver('TestResolver4', er_diagram=diagram)
    # owner_id is not in the subset selection but auto-added with exclude=True
    # Provide owner_id explicitly to test the full flow
    data = TaskCard(id=1, title="task1", owner_id=1)
    assert 'owner_id' in TaskCard.model_fields
    assert TaskCard.model_fields['owner_id'].exclude is True

    result = await MyResolver().resolve(data)
    assert result.owner is not None
    assert result.owner.name == "alice"
    # owner_id should be excluded from serialization
    dumped = result.model_dump()
    assert 'owner_id' not in dumped


# === Test 5: Explicit + Implicit coexistence ===

class Biz(BaseModel):
    id: int
    name: str
    user_id: int
    manager_id: int


class BizEntity(Biz, BASE_ENTITY):
    __relationships__ = [
        Relationship(fk='user_id', name='user', target=User, loader=UserLoader),
        Relationship(fk='manager_id', name='manager', target=User, loader=UserLoader),
    ]


class BizView(BizEntity):
    user: Optional[User] = None  # implicit
    my_manager: Annotated[Optional[User], AutoLoad(origin='manager')] = None  # explicit with origin


@pytest.mark.asyncio
async def test_explicit_and_implicit_coexist():
    """Both explicit (with origin) and implicit AutoLoad work together."""
    diagram2 = BASE_ENTITY.get_diagram()
    MyResolver = config_resolver('TestResolver5', er_diagram=diagram2)
    data = BizView(id=1, name="biz1", user_id=1, manager_id=2)
    result = await MyResolver().resolve(data)
    assert result.user.name == "alice"
    assert result.my_manager.name == "bob"


# === Test 6: resolve_* conflict warning ===

class TaskWithResolve(Task):
    owner: Optional[User] = None  # implicit would match

    def resolve_owner(self, loader=Loader(UserLoader)):
        """Manual resolve takes priority."""
        return loader.load(self.owner_id)


@pytest.mark.asyncio
async def test_resolve_conflict_warning(caplog):
    """Manual resolve_* takes priority, warning emitted."""
    MyResolver = config_resolver('TestResolver6', er_diagram=diagram)
    data = TaskWithResolve(id=1, title="task1", owner_id=1)
    with caplog.at_level(logging.WARNING, logger="pydantic_resolve.utils.er_diagram"):
        result = await MyResolver().resolve(data)
    assert result.owner is not None
    assert result.owner.name == "alice"
    assert any('implicit AutoLoad' in record.message and 'owner' in record.message
               for record in caplog.records)


# === Test 7: Origin parameter still requires explicit annotation ===

class TaskWithAlias(Task):
    my_owner: Annotated[Optional[User], AutoLoad(origin='owner')] = None


@pytest.mark.asyncio
async def test_origin_still_requires_explicit():
    """Field name != relationship name requires explicit AutoLoad(origin=...)."""
    MyResolver = config_resolver('TestResolver7', er_diagram=diagram)
    data = TaskWithAlias(id=1, title="task1", owner_id=1)
    result = await MyResolver().resolve(data)
    assert result.my_owner is not None
    assert result.my_owner.name == "alice"


class TaskAliasCard(DefineSubset):
    __pydantic_resolve_subset__ = (Task, ['id', 'title'])

    my_owner: Annotated[Optional[User], AutoLoad(origin='owner')] = None


@pytest.mark.asyncio
async def test_origin_subset_fk_auto_add():
    """Explicit AutoLoad(origin=...) still auto-adds the hidden FK field."""
    MyResolver = config_resolver('TestResolver7Subset', er_diagram=diagram)
    assert 'owner_id' in TaskAliasCard.model_fields
    assert TaskAliasCard.model_fields['owner_id'].exclude is True

    data = TaskAliasCard(id=1, title="task1", owner_id=1)
    result = await MyResolver().resolve(data)
    assert result.my_owner is not None
    assert result.my_owner.name == "alice"
    assert 'owner_id' not in result.model_dump()


# === Test 8: Type incompatibility silently skipped ===

class TaskWrongType(Task):
    owner: str = ""  # name matches 'owner' relationship, but type is incompatible


@pytest.mark.asyncio
async def test_type_mismatch_silent_skip():
    """Incompatible type is silently skipped, no error."""
    MyResolver = config_resolver('TestResolver8', er_diagram=diagram)
    data = TaskWrongType(id=1, title="task1", owner_id=1)
    result = await MyResolver().resolve(data)
    assert result.owner == ""  # unchanged, no resolve method generated


# === Test 9: No diagram registration, no implicit matching ===

class UnregisteredEntity(BaseModel):
    id: int
    name: str


class UnregisteredView(UnregisteredEntity):
    owner: Optional[User] = None  # no relationship, no implicit matching


@pytest.mark.asyncio
async def test_no_diagram_no_implicit():
    """Classes not registered in diagram are unaffected."""
    MyResolver = config_resolver('TestResolver9', er_diagram=diagram)
    data = UnregisteredView(id=1, name="test", owner=None)
    result = await MyResolver().resolve(data)
    assert result.owner is None  # no resolve method generated


def test_external_er_diagram_ambiguity_raises():
    """Conflicting external diagrams must fail loudly instead of silently winning by last write."""

    class ExternalUser(BaseModel):
        id: int

    class ExternalTask(BaseModel):
        id: int
        owner_id: int
        manager_id: int

    ErDiagram(entities=[
        dict(
            kls=ExternalTask,
            relationships=[
                dict(fk='owner_id', name='user', target=ExternalUser, loader=UserLoader),
            ],
        )
    ])
    ErDiagram(entities=[
        dict(
            kls=ExternalTask,
            relationships=[
                dict(fk='manager_id', name='user', target=ExternalUser, loader=UserLoader),
            ],
        )
    ])

    with pytest.raises(ValueError, match='Ambiguous external ErDiagram relationship "user"'):
        class ExternalTaskSubset(DefineSubset):
            __pydantic_resolve_subset__ = (ExternalTask, ['id'])

            user: Optional[ExternalUser] = None


# === Test 10: Scalar target type with AutoLoad(origin=...) ===

class TagNameLoader(DataLoader):
    async def batch_load_fn(self, keys):
        tag_map = {1: "python", 2: "rust", 3: "go"}
        return [tag_map.get(k) for k in keys]


class TagEntity(BaseModel, BASE_ENTITY):
    __relationships__ = [
        Relationship(fk='tag_id', name='tag_name', target=str, loader=TagNameLoader),
    ]
    id: int
    tag_id: int


class TagView(TagEntity):
    my_tag: Annotated[Optional[str], AutoLoad(origin='tag_name')] = None


@pytest.mark.asyncio
async def test_scalar_target_explicit_origin():
    """Scalar target (str) works with explicit AutoLoad(origin=...)."""
    diagram2 = BASE_ENTITY.get_diagram()
    MyResolver = config_resolver('TestResolver10', er_diagram=diagram2)
    data = TagView(id=1, tag_id=2)
    result = await MyResolver().resolve(data)
    assert result.my_tag == "rust"


# === Test 11: Scalar target implicit matching ===

class TagViewImplicit(TagEntity):
    tag_name: Optional[str] = None  # implicit: matches relationship 'tag_name'


@pytest.mark.asyncio
async def test_scalar_target_implicit():
    """Scalar target (str) works with implicit matching."""
    diagram3 = BASE_ENTITY.get_diagram()
    MyResolver = config_resolver('TestResolver11', er_diagram=diagram3)
    data = TagViewImplicit(id=1, tag_id=3)
    result = await MyResolver().resolve(data)
    assert result.tag_name == "go"


# === Test 12: Scalar target in DefineSubset ===

class TagSummary(DefineSubset):
    __pydantic_resolve_subset__ = (TagEntity, ['id'])

    my_tag: Annotated[Optional[str], AutoLoad(origin='tag_name')] = None


@pytest.mark.asyncio
async def test_scalar_target_subset_with_origin():
    """Scalar target in DefineSubset with explicit origin auto-injects FK."""
    diagram4 = BASE_ENTITY.get_diagram()
    MyResolver = config_resolver('TestResolver12', er_diagram=diagram4)
    assert 'tag_id' in TagSummary.model_fields
    assert TagSummary.model_fields['tag_id'].exclude is True

    data = TagSummary(id=1, tag_id=1)
    result = await MyResolver().resolve(data)
    assert result.my_tag == "python"
    assert 'tag_id' not in result.model_dump()
