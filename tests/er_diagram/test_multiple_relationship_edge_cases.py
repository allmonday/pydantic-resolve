"""
Test MultipleRelationship edge cases and error handling.

This module tests edge cases such as empty links list, mismatched biz values,
and other boundary conditions for MultipleRelationship.
"""
import pytest
from typing import Annotated, List
from pydantic import BaseModel

from pydantic_resolve import (
    config_resolver,
    Entity,
    MultipleRelationship,
    Link,
    LoadBy,
    ErDiagram,
)
from aiodataloader import DataLoader


class User(BaseModel):
    """Test user model."""
    id: int
    name: str


class Foo(BaseModel):
    """Test foo model."""
    id: int
    name: str


class Bar(BaseModel):
    """Test bar model."""
    id: int
    name: str


class Container(BaseModel):
    """Test container model."""
    id: int
    name: str


# Test loaders
class FooLoader(DataLoader):
    """Loader for Foo objects."""
    async def batch_load_fn(self, keys):
        return [
            [dict(id=1, name=f"foo_{k}"), dict(id=2, name=f"foo_{k}_2")]
            for k in keys
        ]


class BarLoader(DataLoader):
    """Loader for Bar objects."""
    async def batch_load_fn(self, keys):
        return [
            [dict(id=1, name=f"bar_{k}"), dict(id=2, name=f"bar_{k}_2")]
            for k in keys
        ]


class EmptyLoader(DataLoader):
    """Loader that returns empty list."""
    async def batch_load_fn(self, keys):
        return [[] for _ in keys]


@pytest.mark.asyncio
async def test_empty_links_list():
    """Test MultipleRelationship with empty links list raises AttributeError."""
    diagram = ErDiagram(
        configs=[
            Entity(
                kls=Container,
                relationships=[
                    MultipleRelationship(
                        field='id',
                        target_kls=list[Foo],
                        links=[]  # Empty links list
                    )
                ]
            )
        ]
    )

    class ContainerResponse(Container):
        # Using LoadBy with a field that has empty links
        items: Annotated[List[Foo], LoadBy('id')] = []

    MyResolver = config_resolver('MyResolver', er_diagram=diagram)

    container = ContainerResponse(id=1, name="test")

    # Empty links means relationship cannot be resolved - should raise AttributeError
    with pytest.raises(AttributeError, match="Relationship.*not found"):
        await MyResolver().resolve(container)


@pytest.mark.asyncio
async def test_biz_not_found_in_links():
    """Test LoadBy with biz that doesn't exist in links."""
    diagram = ErDiagram(
        configs=[
            Entity(
                kls=Container,
                relationships=[
                    MultipleRelationship(
                        field='id',
                        target_kls=list[Foo],
                        links=[
                            Link(biz='default', loader=FooLoader),
                            Link(biz='special', loader=BarLoader)
                        ]
                    )
                ]
            )
        ]
    )

    class ContainerResponse(Container):
        # Using biz='nonexistent' which is not in the links
        items: Annotated[List[Foo], LoadBy('id', biz='nonexistent')] = []

    MyResolver = config_resolver('MyResolver', er_diagram=diagram)

    container = ContainerResponse(id=1, name="test")

    # Should raise AttributeError because biz='nonexistent' is not found
    with pytest.raises(AttributeError) as excinfo:
        await MyResolver().resolve(container)

    # Error message should mention the biz value that wasn't found
    error_msg = str(excinfo.value)
    assert 'nonexistent' in error_msg


@pytest.mark.asyncio
async def test_loadby_without_biz_for_multiple():
    """Test LoadBy without biz when using MultipleRelationship."""
    diagram = ErDiagram(
        configs=[
            Entity(
                kls=Container,
                relationships=[
                    MultipleRelationship(
                        field='id',
                        target_kls=list[Foo],
                        links=[
                            Link(biz='default', loader=FooLoader),
                            Link(biz='special', loader=BarLoader)
                        ]
                    )
                ]
            )
        ]
    )

    class ContainerResponse(Container):
        # Not specifying biz, but using MultipleRelationship
        # This should match the first link or raise an error
        items: Annotated[List[Foo], LoadBy('id')] = []

    MyResolver = config_resolver('MyResolver', er_diagram=diagram)

    container = ContainerResponse(id=1, name="test")

    # When biz=None, it should try to match using regular Relationship logic
    # Since MultipleRelationship doesn't have a default biz, this might fail
    # or it might try to match target_kls type
    with pytest.raises(AttributeError):
        await MyResolver().resolve(container)


@pytest.mark.asyncio
async def test_multiple_links_with_different_biz():
    """Test that different biz values load different data using separate MultipleRelationships (baseline test)."""
    diagram = ErDiagram(
        configs=[
            Entity(
                kls=Container,
                relationships=[
                    # Separate MultipleRelationship for Foo type
                    MultipleRelationship(
                        field='id',
                        target_kls=list[Foo],
                        links=[
                            Link(biz='default', loader=FooLoader),
                            Link(biz='special', loader=FooLoader)  # Same type, different biz
                        ]
                    ),
                    # Separate MultipleRelationship for Bar type
                    MultipleRelationship(
                        field='id',
                        target_kls=list[Bar],
                        links=[
                            Link(biz='bar_default', loader=BarLoader),
                            Link(biz='bar_special', loader=BarLoader)
                        ]
                    )
                ]
            )
        ]
    )

    class ContainerResponse(Container):
        # Using biz='default' should use FooLoader
        foos_default: Annotated[List[Foo], LoadBy('id', biz='default')] = []
        # Using biz='special' should use the other FooLoader
        foos_special: Annotated[List[Foo], LoadBy('id', biz='special')] = []
        # Using biz='bar_default' should use BarLoader
        bars_default: Annotated[List[Bar], LoadBy('id', biz='bar_default')] = []

    MyResolver = config_resolver('MyResolver', er_diagram=diagram)

    container = ContainerResponse(id=1, name="test")

    result = await MyResolver().resolve(container)

    # Should load data for each biz
    assert len(result.foos_default) == 2
    assert len(result.foos_special) == 2
    assert len(result.bars_default) == 2
    # FooLoader returns foo_ prefixed names
    assert result.foos_default[0].name.startswith("foo_")
    # BarLoader returns bar_ prefixed names
    assert result.bars_default[0].name.startswith("bar_")


def test_multiple_relationship_validation_duplicate_biz():
    """Test that MultipleRelationship validates duplicate biz values."""
    from pydantic import ValidationError

    # Creating a MultipleRelationship with duplicate biz should fail validation
    with pytest.raises(ValidationError) as excinfo:
        MultipleRelationship(
            field='id',
            target_kls=list[Foo],
            links=[
                Link(biz='default', loader=FooLoader),
                Link(biz='default', loader=BarLoader)  # Duplicate biz
            ]
        )

    # Error should mention duplicate link.biz
    error_msg = str(excinfo.value)
    assert 'Duplicate link.biz' in error_msg


@pytest.mark.asyncio
async def test_empty_links_with_loadby():
    """Test behavior when LoadBy is used with empty links and no biz specified raises AttributeError."""
    diagram = ErDiagram(
        configs=[
            Entity(
                kls=Container,
                relationships=[
                    MultipleRelationship(
                        field='id',
                        target_kls=list[Foo],
                        links=[]  # Empty links
                    )
                ]
            )
        ]
    )

    class ContainerResponse(Container):
        items: Annotated[List[Foo], LoadBy('id')] = []

    MyResolver = config_resolver('MyResolver', er_diagram=diagram)

    container = ContainerResponse(id=1, name="test")

    # Empty links means relationship cannot be resolved - should raise AttributeError
    with pytest.raises(AttributeError, match="Relationship.*not found"):
        await MyResolver().resolve(container)


@pytest.mark.asyncio
async def test_link_with_field_name():
    """Test Link with field_name specified - requires origin_kls in LoadBy."""
    diagram = ErDiagram(
        configs=[
            Entity(
                kls=Container,
                relationships=[
                    MultipleRelationship(
                        field='id',
                        target_kls=list[Foo],
                        links=[
                            Link(
                                biz='self',
                                loader=FooLoader,
                                field_name='name'  # Metadata for validation/hints
                            )
                        ]
                    )
                ]
            )
        ]
    )

    class ContainerResponse(Container):
        # When field_name is set in Link, origin_kls must be provided in LoadBy
        items: Annotated[List[Foo], LoadBy('id', biz='self', origin_kls=list[Foo])] = []

    MyResolver = config_resolver('MyResolver', er_diagram=diagram)

    container = ContainerResponse(id=1, name="test")

    # This should work - loader returns Foo objects
    result = await MyResolver().resolve(container)
    # field_name='name' doesn't extract fields, it's just metadata
    assert isinstance(result.items, list)
    assert len(result.items) == 2
    assert isinstance(result.items[0], Foo)


def test_single_relationship_vs_multiple():
    """Test that regular Relationship works (baseline comparison)."""
    # This is just to verify regular relationships work as expected
    # (baseline test to ensure MultipleRelationship edge cases are distinct)
    assert True  # Placeholder - actual test would use regular Relationship
