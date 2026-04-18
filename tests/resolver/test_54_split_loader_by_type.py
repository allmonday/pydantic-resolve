import pytest
from typing import List, Optional
from pydantic import BaseModel
from aiodataloader import DataLoader
from pydantic_resolve import Loader, Resolver


class TaskLoader(DataLoader):
    async def batch_load_fn(self, keys):
        return [[dict(id=k, title=f'task-{k}', desc=f'desc-{k}', status='open',
                       owner_id=1, created_at='2024-01-01')] for k in keys]


class TaskCard(BaseModel):
    id: int
    title: str


class TaskDetail(BaseModel):
    id: int
    title: str
    desc: str
    status: str
    owner_id: int
    created_at: str


class Dashboard(BaseModel):
    id: int
    cards: List[TaskCard] = []
    details: List[TaskDetail] = []

    def resolve_cards(self, loader=Loader(TaskLoader)):
        return loader.load(self.id)

    def resolve_details(self, loader=Loader(TaskLoader)):
        return loader.load(self.id)


@pytest.mark.asyncio
async def test_default_no_split_fields_are_unioned():
    """Default split_loader_by_type=False, all request_type fields are unioned."""
    dashboard = Dashboard(id=1)
    resolver = Resolver()
    await resolver.resolve(dashboard)

    loader_instance = resolver.loader_instance_cache[
        'tests.resolver.test_54_split_loader_by_type.TaskLoader']
    assert set(loader_instance._query_meta['fields']) == {
        'id', 'title', 'desc', 'status', 'owner_id', 'created_at'}


@pytest.mark.asyncio
async def test_split_creates_separate_instances_with_own_query_meta():
    """split_loader_by_type=True creates separate loader instances per request_type."""
    dashboard = Dashboard(id=1)
    resolver = Resolver(split_loader_by_type=True)
    await resolver.resolve(dashboard)

    loader_path = 'tests.resolver.test_54_split_loader_by_type.TaskLoader'
    inner = resolver.loader_instance_cache[loader_path]

    card_loader = inner[(TaskCard,)]
    detail_loader = inner[(TaskDetail,)]

    assert set(card_loader._query_meta['fields']) == {'id', 'title'}
    assert card_loader._query_meta['request_types'] == [
        {'name': TaskCard, 'fields': ['id', 'title']}
    ]

    assert set(detail_loader._query_meta['fields']) == {
        'id', 'title', 'desc', 'status', 'owner_id', 'created_at'}
    assert detail_loader._query_meta['request_types'] == [
        {'name': TaskDetail, 'fields': ['id', 'title', 'desc', 'status', 'owner_id', 'created_at']}
    ]


@pytest.mark.asyncio
async def test_split_produces_correct_resolve_results():
    """split_loader_by_type=True still produces correct resolve results."""
    dashboard = Dashboard(id=1)
    resolver = Resolver(split_loader_by_type=True)
    result = await resolver.resolve(dashboard)

    assert len(result.cards) == 1
    assert result.cards[0].id == 1
    assert result.cards[0].title == 'task-1'

    assert len(result.details) == 1
    assert result.details[0].id == 1
    assert result.details[0].status == 'open'


class SprintBoard(BaseModel):
    id: int
    tasks_a: List[TaskCard] = []
    tasks_b: List[TaskCard] = []

    def resolve_tasks_a(self, loader=Loader(TaskLoader)):
        return loader.load(self.id)

    def resolve_tasks_b(self, loader=Loader(TaskLoader)):
        return loader.load(self.id)


@pytest.mark.asyncio
async def test_same_request_type_shares_split_instance():
    """Same request_type across different resolve methods shares one split loader."""
    board = SprintBoard(id=1)
    resolver = Resolver(split_loader_by_type=True)
    await resolver.resolve(board)

    loader_path = 'tests.resolver.test_54_split_loader_by_type.TaskLoader'
    assert loader_path in resolver.loader_instance_cache
    inner = resolver.loader_instance_cache[loader_path]
    assert (TaskCard,) in inner
    assert (TaskDetail,) not in inner


class SimpleView(BaseModel):
    id: int
    tasks: List[TaskCard] = []

    def resolve_tasks(self, loader=Loader(TaskLoader)):
        return loader.load(self.id)


@pytest.mark.asyncio
async def test_single_request_type_behaves_same_with_or_without_split():
    """With only one request_type, split and no-split produce same _query_meta."""
    resolver_no_split = Resolver()
    await resolver_no_split.resolve(SimpleView(id=1))
    loader_no_split = resolver_no_split.loader_instance_cache[
        'tests.resolver.test_54_split_loader_by_type.TaskLoader']

    resolver_split = Resolver(split_loader_by_type=True)
    await resolver_split.resolve(SimpleView(id=1))
    loader_split = resolver_split.loader_instance_cache[
        'tests.resolver.test_54_split_loader_by_type.TaskLoader'][(TaskCard,)]

    assert set(loader_no_split._query_meta['fields']) == set(loader_split._query_meta['fields'])


class TrackingTaskLoader(DataLoader):
    query_count = 0

    async def batch_load_fn(self, keys):
        TrackingTaskLoader.query_count += 1
        return [[dict(id=k, title=f'task-{k}', desc=f'desc-{k}', status='open',
                       owner_id=1, created_at='2024-01-01')] for k in keys]


class TrackDashboard(BaseModel):
    id: int
    cards: List[TaskCard] = []
    details: List[TaskDetail] = []

    def resolve_cards(self, loader=Loader(TrackingTaskLoader)):
        return loader.load(self.id)

    def resolve_details(self, loader=Loader(TrackingTaskLoader)):
        return loader.load(self.id)


@pytest.mark.asyncio
async def test_split_causes_separate_queries_for_same_key():
    """Split loaders query same key independently (documented tradeoff)."""
    TrackingTaskLoader.query_count = 0

    resolver = Resolver()
    await resolver.resolve(TrackDashboard(id=1))
    assert TrackingTaskLoader.query_count == 1

    TrackingTaskLoader.query_count = 0

    resolver = Resolver(split_loader_by_type=True)
    await resolver.resolve(TrackDashboard(id=1))
    assert TrackingTaskLoader.query_count == 2


@pytest.mark.asyncio
async def test_split_with_loader_instances_raises_error():
    """split_loader_by_type=True is incompatible with pre-created loader_instances."""
    pre_created = {TaskLoader: TaskLoader()}
    resolver = Resolver(
        split_loader_by_type=True,
        loader_instances=pre_created
    )

    with pytest.raises(ValueError, match='split_loader_by_type=True is incompatible with loader_instances'):
        await resolver.resolve(Dashboard(id=1))
