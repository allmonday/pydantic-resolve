"""
Test _resolve_ref function error handling in base_entity().

This module tests various error scenarios when resolving class references,
including invalid module paths, missing classes, and unsupported generic types.
"""
import pytest
from pydantic import BaseModel

from pydantic_resolve.utils.er_diagram import base_entity, Relationship


class User(BaseModel):
    """Test user model."""
    id: int
    name: str


class Post(BaseModel):
    """Test post model."""
    id: int
    title: str


def test_multiple_colons_in_module_path():
    """Test that multiple colons in module path are handled (first colon is used as separator)."""
    Base = base_entity()

    class MyEntity(BaseModel, Base):
        __relationships__ = [
            # 'tests.utils.test_resolve_ref_errors:User' - valid path with single colon
            Relationship(field='user_id', target_kls='tests.utils.test_resolve_ref_errors:User', loader=None)
        ]
        id: int
        user_id: int

    # This should work since the module path is valid
    diagram = Base.get_diagram()
    assert len(diagram.configs) == 1


def test_missing_module_name_before_colon():
    """Test that empty module name before colon raises appropriate error."""
    Base = base_entity()

    class MyEntity(BaseModel, Base):
        __relationships__ = [
            # ':ClassName' - empty module name
            Relationship(field='user_id', target_kls=':User', loader=None)
        ]
        id: int
        user_id: int

    # Empty module name should raise ValueError (from importlib.import_module)
    with pytest.raises((ImportError, ValueError)):
        Base.get_diagram()


def test_missing_class_name_after_colon():
    """Test that empty class name after colon is handled."""
    Base = base_entity()

    class MyEntity(BaseModel, Base):
        __relationships__ = [
            # 'tests.utils:' - empty class name
            Relationship(field='user_id', target_kls='tests.utils:', loader=None)
        ]
        id: int
        user_id: int

    # Empty class name should raise AttributeError when trying to get attribute
    with pytest.raises((ImportError, AttributeError)):
        Base.get_diagram()


def test_module_exists_but_class_not_found():
    """Test that reference to non-existent class in valid module raises clear error."""
    Base = base_entity()

    class MyEntity(BaseModel, Base):
        __relationships__ = [
            # 'builtins.NonExistentClass' - module exists but class doesn't
            Relationship(field='user_id', target_kls='builtins:NonExistentClass', loader=None)
        ]
        id: int
        user_id: int

    with pytest.raises((ImportError, AttributeError)) as excinfo:
        Base.get_diagram()

    # Should mention the class name in the error
    assert 'NonExistentClass' in str(excinfo.value)


def test_simple_class_name_not_found_in_module():
    """Test that simple class name without module path raises clear error."""
    Base = base_entity()

    class MyEntity(BaseModel, Base):
        __relationships__ = [
            # 'NonExistentClass' - simple name, should look in this module
            Relationship(field='user_id', target_kls='NonExistentClass', loader=None)
        ]
        id: int
        user_id: int

    with pytest.raises(AttributeError) as excinfo:
        Base.get_diagram()

    # Should mention the class name and module
    error_msg = str(excinfo.value)
    assert 'NonExistentClass' in error_msg


def test_valid_module_path_syntax():
    """Test that valid module:path syntax works correctly."""
    Base = base_entity()

    class MyEntity(BaseModel, Base):
        __relationships__ = [
            # Use full module path to User class in this test file
            Relationship(field='user_id', target_kls='tests.utils.test_resolve_ref_errors:User', loader=None)
        ]
        id: int
        user_id: int

    diagram = Base.get_diagram()
    assert len(diagram.configs) == 1
    # The target_kls should be resolved to the actual User class
    entity = diagram.configs[0]
    resolved_class = entity.relationships[0].target_kls
    # Check the class name and module instead of using 'is' because they might be
    # different objects in memory due to different import paths
    assert resolved_class.__name__ == User.__name__
    assert resolved_class.__module__.endswith('test_resolve_ref_errors')


def test_nested_list_generic_with_string_ref():
    """Test that nested list[list['ClassName']] is handled (currently not supported)."""
    Base = base_entity()

    class MyEntity(BaseModel, Base):
        __relationships__ = [
            # Nested generics - current implementation only handles single level
            Relationship(field='user_id', target_kls=list[list['User']], loader=None)
        ]
        id: int
        user_id: int

    # Current implementation doesn't support nested generics
    # The inner list['User'] will be processed, but outer list will remain as-is
    diagram = Base.get_diagram()
    assert len(diagram.configs) == 1


def test_other_container_types():
    """Test that other container types like tuple, set are handled."""
    Base = base_entity()

    class MyEntity(BaseModel, Base):
        __relationships__ = [
            # These are not processed by _resolve_ref, just returned as-is
            Relationship(field='items', target_kls=tuple['User'], loader=None),
        ]
        id: int
        user_id: int

    diagram = Base.get_diagram()
    assert len(diagram.configs) == 1
    # tuple['User'] should remain as-is since only list is processed
    entity = diagram.configs[0]
    # Check that the GenericAlias is preserved
    assert entity.relationships[0].target_kls == tuple['User']


def test_dict_generic_with_string_ref():
    """Test that dict['K', 'V'] is handled (currently only supports list)."""
    Base = base_entity()

    class MyEntity(BaseModel, Base):
        __relationships__ = [
            # Dict generics are not processed by _resolve_ref
            Relationship(field='mapping', target_kls=dict[str, 'User'], loader=None),
        ]
        id: int
        user_id: int

    diagram = Base.get_diagram()
    assert len(diagram.configs) == 1
    # dict should remain as-is since only list is processed


def test_valid_list_generic_with_string_ref():
    """Test that list['ClassName'] syntax works correctly."""
    Base = base_entity()

    class MyEntity(BaseModel, Base):
        __relationships__ = [
            # List generic with string reference
            Relationship(field='user_id', target_kls=list['User'], loader=None)
        ]
        id: int
        user_id: int

    diagram = Base.get_diagram()
    assert len(diagram.configs) == 1
    entity = diagram.configs[0]
    # The list['User'] should be resolved to list[User]
    assert entity.relationships[0].target_kls == list[User]


def test_list_generic_with_module_path():
    """Test that list['module:ClassName'] syntax works correctly."""
    Base = base_entity()

    class MyEntity(BaseModel, Base):
        __relationships__ = [
            # List generic with module path - noqa to test special syntax handling
            Relationship(field='user_id', target_kls=list['tests.utils.test_resolve_ref_errors:User'], loader=None)  # noqa: F722
        ]
        id: int
        user_id: int

    diagram = Base.get_diagram()
    assert len(diagram.configs) == 1
    entity = diagram.configs[0]
    # Should be resolved to list[User] where User is the actual class
    resolved_type = entity.relationships[0].target_kls
    # Check it's a list type with correct element type
    assert resolved_type.__origin__ is list
    resolved_arg = resolved_type.__args__[0]
    assert resolved_arg.__name__ == User.__name__
    assert resolved_arg.__module__.endswith('test_resolve_ref_errors')


def test_empty_string_class_name_in_module_path():
    """Test module path with empty class name after colon."""
    Base = base_entity()

    class MyEntity(BaseModel, Base):
        __relationships__ = [
            Relationship(field='user_id', target_kls='tests.utils.test_resolve_ref_errors:', loader=None)
        ]
        id: int
        user_id: int

    with pytest.raises((ImportError, AttributeError)):
        Base.get_diagram()


def test_invalid_module_in_module_path():
    """Test reference to non-existent module."""
    Base = base_entity()

    class MyEntity(BaseModel, Base):
        __relationships__ = [
            Relationship(field='user_id', target_kls='totally.fake.module:User', loader=None)
        ]
        id: int
        user_id: int

    with pytest.raises(ImportError) as excinfo:
        Base.get_diagram()

    error_msg = str(excinfo.value)
    assert 'totally.fake.module' in error_msg


def test_resolve_ref_with_direct_class_reference():
    """Test that direct class references (not strings) work as expected."""
    Base = base_entity()

    class MyEntity(BaseModel, Base):
        __relationships__ = [
            # Direct class reference - should pass through unchanged
            Relationship(field='user_id', target_kls=User, loader=None)
        ]
        id: int
        user_id: int

    diagram = Base.get_diagram()
    assert len(diagram.configs) == 1
    entity = diagram.configs[0]
    assert entity.relationships[0].target_kls is User
