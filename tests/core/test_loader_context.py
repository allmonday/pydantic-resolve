from __future__ import annotations
import pytest
from pydantic import BaseModel
from aiodataloader import DataLoader
from pydantic_resolve.analysis import _loader_requires_context
from pydantic_resolve import Resolver, LoaderDepend, LoaderContextNotProvidedError


# Test 1: Loader with _context attribute
class LoaderWithContext(DataLoader):
    _context: dict

    async def batch_load_fn(self, keys):
        user_id = self._context.get('user_id')
        # Return a simple value for each key
        return [f'{k}-{user_id}' for k in keys]


# Test 2: Loader without _context attribute
class LoaderWithoutContext(DataLoader):
    async def batch_load_fn(self, keys):
        return keys


class ModelWithContextLoader(BaseModel):
    name: str
    value: str = ''

    def resolve_value(self, loader=LoaderDepend(LoaderWithContext)):
        return loader.load(self.name)


class ModelWithoutContextLoader(BaseModel):
    name: str
    value: str = ''

    def resolve_value(self, loader=LoaderDepend(LoaderWithoutContext)):
        return loader.load(self.name)


class ModelWithMixedLoaders(BaseModel):
    name: str
    field1: str = ''
    field2: str = ''

    def resolve_field1(self, loader=LoaderDepend(LoaderWithContext)):
        return loader.load(self.name)

    def resolve_field2(self, loader=LoaderDepend(LoaderWithoutContext)):
        return loader.load(self.name)


# ==================== Unit Tests ====================


def test_loader_requires_context_detection():
    """Test that _loader_requires_context correctly detects _context attribute."""
    assert _loader_requires_context(LoaderWithContext) is True
    assert _loader_requires_context(LoaderWithoutContext) is False
    # Function-based loader should return False
    async def func_loader(keys):
        return keys
    assert _loader_requires_context(func_loader) is False


@pytest.mark.asyncio
async def test_loader_with_context_requires_resolver_context():
    """Test that loader requiring context raises error when Resolver has no context."""
    model = ModelWithContextLoader(name='test')

    with pytest.raises(LoaderContextNotProvidedError) as exc_info:
        await Resolver().resolve(model)

    assert 'LoaderWithContext' in str(exc_info.value)
    assert 'context' in str(exc_info.value)


@pytest.mark.asyncio
async def test_loader_with_context_works_with_resolver_context():
    """Test that loader requiring context works when Resolver provides context."""
    model = ModelWithContextLoader(name='test')
    context = {'user_id': 123}

    result = await Resolver(context=context).resolve(model)
    assert result is not None
    assert result.value == 'test-123'


@pytest.mark.asyncio
async def test_loader_without_context_works_without_resolver_context():
    """Test that loader without context works even when Resolver has no context."""
    model = ModelWithoutContextLoader(name='test')
    result = await Resolver().resolve(model)
    assert result is not None
    assert result.value == 'test'


@pytest.mark.asyncio
async def test_loader_context_is_set_on_instance():
    """Test that context is actually set on the loader instance."""
    model = ModelWithContextLoader(name='test')
    context = {'user_id': 123, 'role': 'admin'}

    resolver = Resolver(context=context)
    result = await resolver.resolve(model)

    # Check the loader instance in cache
    found = False
    for path, instance in resolver.loader_instance_cache.items():
        if 'LoaderWithContext' in path:
            assert hasattr(instance, '_context')
            assert instance._context == context
            found = True
            break

    assert found, "LoaderWithContext not found in cache"
    assert result.value == 'test-123'


@pytest.mark.asyncio
async def test_mixed_loaders_missing_context_error():
    """Test that error is raised when any loader needs context."""
    model = ModelWithMixedLoaders(name='test')

    with pytest.raises(LoaderContextNotProvidedError) as exc_info:
        await Resolver().resolve(model)

    assert 'LoaderWithContext' in str(exc_info.value)


@pytest.mark.asyncio
async def test_mixed_loaders_with_context():
    """Test that mixed loaders work when context is provided."""
    model = ModelWithMixedLoaders(name='test')
    context = {'user_id': 456}

    result = await Resolver(context=context).resolve(model)

    assert result is not None
    assert result.field1 == 'test-456'
    # field2 returns the key itself (string), loader returns it unchanged
    assert result.field2 == 'test'
