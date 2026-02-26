"""Tests for duplicate entity name detection in ErDiagram."""

import pytest
from pydantic import BaseModel

from pydantic_resolve.utils.er_diagram import ErDiagram, Entity


def test_duplicate_entity_names_raises_error():
    """Test that duplicate entity names from different modules raise an error."""

    class UserEntityA(BaseModel):
        id: int
        name: str

    class UserEntityB(BaseModel):
        id: int
        email: str

    # Simulate same class name from different modules
    UserEntityA.__name__ = "UserEntity"
    UserEntityA.__module__ = "module_a.user"
    UserEntityB.__name__ = "UserEntity"
    UserEntityB.__module__ = "module_b.user"

    with pytest.raises(ValueError) as exc_info:
        ErDiagram(configs=[
            Entity(kls=UserEntityA, relationships=[]),
            Entity(kls=UserEntityB, relationships=[]),
        ])

    assert "Duplicate entity name 'UserEntity' detected" in str(exc_info.value)
    assert "module_a.user" in str(exc_info.value)
    assert "module_b.user" in str(exc_info.value)


def test_different_entity_names_works():
    """Test that different entity names work correctly."""

    class UserEntity(BaseModel):
        id: int
        name: str

    class PostEntity(BaseModel):
        id: int
        title: str

    # Should not raise any error
    diagram = ErDiagram(configs=[
        Entity(kls=UserEntity, relationships=[]),
        Entity(kls=PostEntity, relationships=[]),
    ])
    assert len(diagram.configs) == 2


def test_same_class_twice_raises_error():
    """Test that registering the same class twice raises an error (existing behavior)."""

    class UserEntity(BaseModel):
        id: int
        name: str

    with pytest.raises(ValueError) as exc_info:
        ErDiagram(configs=[
            Entity(kls=UserEntity, relationships=[]),
            Entity(kls=UserEntity, relationships=[]),
        ])

    assert "Duplicate config.kls detected" in str(exc_info.value)
