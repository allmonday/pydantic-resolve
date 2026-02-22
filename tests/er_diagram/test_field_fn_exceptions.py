"""
Test field_fn and load_many_fn exception handling in Relationship.

This module tests how exceptions from field_fn and load_many_fn functions
are handled during data resolution.
"""
import pytest
from typing import Optional, Annotated, List
from pydantic import BaseModel

from pydantic_resolve import (
    config_resolver,
    Entity,
    Relationship,
    LoadBy,
    ErDiagram
)
from aiodataloader import DataLoader


class User(BaseModel):
    """Test user model."""
    id: int
    name: str


class Item(BaseModel):
    """Test item model."""
    id: int
    name: str


class Order(BaseModel):
    """Test order model with various field types."""
    id: int = 0
    user_id: int = 0
    user_id_str: Optional[str] = None
    user_ids: List[int] = []
    user_ids_str: Optional[str] = None


# Test loaders
class UserLoader(DataLoader):
    """Loader that returns users."""
    async def batch_load_fn(self, keys):
        # Map keys to user data
        return [
            dict(id=k, name=f"user{k}") if k in [1, 2] else None
            for k in keys
        ]


class ErrorOnNonNumericLoader(DataLoader):
    """Loader that throws error on non-numeric input."""
    async def batch_load_fn(self, keys):
        # This will fail if keys contain non-numeric values
        return [dict(id=int(k), name=f"user{k}") for k in keys]


@pytest.mark.asyncio
async def test_field_fn_raises_value_error():
    """Test that field_fn raising ValueError is propagated."""
    diagram = ErDiagram(
        configs=[
            Entity(
                kls=Order,
                relationships=[
                    Relationship(
                        field='user_id_str',
                        target_kls=User,
                        field_fn=int,  # Will raise ValueError if user_id_str is not numeric
                        loader=ErrorOnNonNumericLoader
                    )
                ]
            )
        ]
    )

    # OrderResponse must inherit from Order to be compatible with the Entity config
    class OrderResponse(Order):
        user: Annotated[Optional[User], LoadBy('user_id_str')] = None

    MyResolver = config_resolver('MyResolver', er_diagram=diagram)

    # Create order with non-numeric user_id_str
    order = OrderResponse(id=1, user_id_str="not_a_number", user_ids=[], user_ids_str='')

    # field_fn should raise ValueError when trying to convert "not_a_number" to int
    # This exception should propagate through the resolver
    with pytest.raises(ValueError, match="invalid literal for int"):
        await MyResolver().resolve(order)


@pytest.mark.asyncio
async def test_field_fn_with_none_value():
    """Test field_fn behavior when field value is None."""
    diagram = ErDiagram(
        configs=[
            Entity(
                kls=Order,
                relationships=[
                    Relationship(
                        field='user_id_str',
                        target_kls=User,
                        field_fn=int,
                        field_none_default=None,  # Return None when field is None
                        loader=UserLoader
                    )
                ]
            )
        ]
    )

    class OrderResponse(Order):
        user: Annotated[Optional[User], LoadBy('user_id_str')] = None

    MyResolver = config_resolver('MyResolver', er_diagram=diagram)

    # Create order with None user_id_str
    order = OrderResponse(id=1, user_id_str=None)

    # Should use field_none_default and return None for user
    result = await MyResolver().resolve(order)
    assert result.user is None


@pytest.mark.asyncio
async def test_field_fn_returns_none():
    """Test field_fn that explicitly returns None causes TypeError from DataLoader."""
    def return_none(x):
        return None

    diagram = ErDiagram(
        configs=[
            Entity(
                kls=Order,
                relationships=[
                    Relationship(
                        field='user_id',
                        target_kls=User,
                        field_fn=return_none,  # Always returns None
                        field_none_default=None,
                        loader=UserLoader
                    )
                ]
            )
        ]
    )

    class OrderResponse(Order):
        user: Annotated[Optional[User], LoadBy('user_id')] = None

    MyResolver = config_resolver('MyResolver', er_diagram=diagram)

    order = OrderResponse(id=1, user_id=1)

    # field_fn returns None, so loader.load(None) is called which throws TypeError
    # field_none_default is only used when the original field value is None, not when field_fn returns None
    with pytest.raises(TypeError, match="loader.load.*must be called with a value"):
        await MyResolver().resolve(order)


@pytest.mark.asyncio
async def test_field_fn_returns_incompatible_type():
    """Test field_fn that returns incompatible type."""
    # field_fn returns string when loader expects int
    diagram = ErDiagram(
        configs=[
            Entity(
                kls=Order,
                relationships=[
                    Relationship(
                        field='user_id',
                        target_kls=User,
                        field_fn=lambda x: "string_instead_of_int",  # Returns str instead of int
                        loader=ErrorOnNonNumericLoader
                    )
                ]
            )
        ]
    )

    class OrderResponse(Order):
        user: Annotated[Optional[User], LoadBy('user_id')] = None

    MyResolver = config_resolver('MyResolver', er_diagram=diagram)

    order = OrderResponse(id=1, user_id=1)

    # The loader will fail because it receives "string_instead_of_int" instead of an int
    with pytest.raises(ValueError):
        await MyResolver().resolve(order)


@pytest.mark.asyncio
async def test_load_many_fn_with_none_field_value():
    """Test load_many_fn behavior when field value is None (returns None by default)."""
    diagram = ErDiagram(
        configs=[
            Entity(
                kls=Order,
                relationships=[
                    Relationship(
                        field='user_ids_str',
                        target_kls=list[User],
                        load_many=True,
                        load_many_fn=lambda x: x.split(','),  # Would fail if called with None
                        loader=UserLoader
                    )
                ]
            )
        ]
    )

    class OrderResponse(Order):
        users: Annotated[List[User], LoadBy('user_ids_str')] = []

    MyResolver = config_resolver('MyResolver', er_diagram=diagram)

    # Create order with None user_ids_str
    order = OrderResponse(id=1, user_ids_str=None)

    # When fk is None and field_none_default_factory is not set, it returns None
    # load_many_fn is NOT called when fk is None
    result = await MyResolver().resolve(order)
    assert result.users is None


@pytest.mark.asyncio
async def test_load_many_fn_returns_none():
    """Test load_many_fn that returns None causes TypeError from DataLoader."""
    diagram = ErDiagram(
        configs=[
            Entity(
                kls=Order,
                relationships=[
                    Relationship(
                        field='user_ids',
                        target_kls=list[User],
                        load_many=True,
                        load_many_fn=lambda x: None,  # Returns None
                        field_none_default_factory=list,
                        loader=UserLoader
                    )
                ]
            )
        ]
    )

    class OrderResponse(Order):
        users: Annotated[List[User], LoadBy('user_ids')] = []

    MyResolver = config_resolver('MyResolver', er_diagram=diagram)

    order = OrderResponse(id=1, user_ids=[1, 2])

    # load_many_fn returns None, so loader.load_many(None) is called which throws TypeError
    # field_none_default_factory is only used when the original field value is None, not when load_many_fn returns None
    with pytest.raises(TypeError, match="must be called with Iterable"):
        await MyResolver().resolve(order)


@pytest.mark.asyncio
async def test_load_many_fn_returns_non_iterable():
    """Test load_many_fn that returns non-iterable value."""
    diagram = ErDiagram(
        configs=[
            Entity(
                kls=Order,
                relationships=[
                    Relationship(
                        field='user_ids',
                        target_kls=list[User],
                        load_many=True,
                        load_many_fn=lambda x: 42,  # Returns int instead of iterable
                        loader=UserLoader
                    )
                ]
            )
        ]
    )

    class OrderResponse(Order):
        users: Annotated[List[User], LoadBy('user_ids')] = []

    MyResolver = config_resolver('MyResolver', er_diagram=diagram)

    order = OrderResponse(id=1, user_ids=[1, 2])

    # The loader will receive 42 (an int) instead of a list of keys
    # This should cause an error when the loader tries to iterate
    with pytest.raises((TypeError, AttributeError)):
        await MyResolver().resolve(order)


@pytest.mark.asyncio
async def test_field_fn_with_valid_transformation():
    """Test field_fn with valid transformation (baseline test)."""
    diagram = ErDiagram(
        configs=[
            Entity(
                kls=Order,
                relationships=[
                    Relationship(
                        field='user_id_str',
                        target_kls=User,
                        field_fn=int,  # Valid: converts string to int
                        loader=UserLoader
                    )
                ]
            )
        ]
    )

    class OrderResponse(Order):
        user: Annotated[Optional[User], LoadBy('user_id_str')] = None

    MyResolver = config_resolver('MyResolver', er_diagram=diagram)

    # Create order with valid numeric string
    order = OrderResponse(id=1, user_id_str="1")

    result = await MyResolver().resolve(order)
    assert result.user is not None
    assert result.user.id == 1


@pytest.mark.asyncio
async def test_load_many_fn_with_valid_transformation():
    """Test load_many_fn with valid transformation (baseline test)."""
    diagram = ErDiagram(
        configs=[
            Entity(
                kls=Order,
                relationships=[
                    Relationship(
                        field='user_ids_str',
                        target_kls=list[User],
                        load_many=True,
                        load_many_fn=lambda x: [int(i) for i in x.split(',')],  # Valid: CSV to list of ints
                        loader=UserLoader
                    )
                ]
            )
        ]
    )

    class OrderResponse(Order):
        users: Annotated[List[User], LoadBy('user_ids_str')] = []

    MyResolver = config_resolver('MyResolver', er_diagram=diagram)

    # Create order with valid CSV string
    order = OrderResponse(id=1, user_ids_str="1,2")

    result = await MyResolver().resolve(order)
    assert len(result.users) == 2
