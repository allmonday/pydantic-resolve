import pytest

"""
Test circular import solutions using module path syntax.

The improved _resolve_ref now supports:
1. Simple class names: 'User' (looked up in the declaring module)
2. Module path syntax: 'path.to.module:ClassName' (lazy import from any module)
3. List generics: list['Foo'] or list['path.to.module:Foo']

This allows avoiding circular imports by using string references with module paths.
"""

def test_circular_import_error():
    """
    Test that module path syntax resolves cross-module references without circular import.

    - entities/user.py uses: list['tests.er_diagram.circular.entities.post:PostEntity']
    - entities/post.py uses: 'tests.er_diagram.circular.entities.user:UserEntity'

    Expected: get_diagram() should successfully resolve both references.
    """
    from tests.er_diagram.circular.entities.user import UserEntity
    from tests.er_diagram.circular.entities.post import PostEntity
    from tests.er_diagram.circular.entities import BaseEntity
    diagram = BaseEntity.get_diagram()
    assert len(diagram.configs) == 2

    # Find UserEntity and PostEntity configs
    user_cfg = next((c for c in diagram.configs if c.kls == UserEntity), None)
    post_cfg = next((c for c in diagram.configs if c.kls == PostEntity), None)

    assert user_cfg is not None, "UserEntity config not found"
    assert post_cfg is not None, "PostEntity config not found"

    # Verify UserEntity has a relationship to list[PostEntity]
    assert len(user_cfg.relationships) == 1
    user_rel = user_cfg.relationships[0]
    assert user_rel.field == 'id'
    # Should be resolved to list[PostEntity], not a string
    assert user_rel.target_kls == list[PostEntity]

    # Verify PostEntity has a relationship to UserEntity
    assert len(post_cfg.relationships) == 1
    post_rel = post_cfg.relationships[0]
    assert post_rel.field == 'user_id'
    # Should be resolved to UserEntity, not a string
    assert post_rel.target_kls == UserEntity


def test_module_path_syntax_with_list():
    """
    Test that module path syntax works with list generic.
    """
    from tests.er_diagram.circular.entities.user import UserEntity
    from tests.er_diagram.circular.entities.post import PostEntity
    from tests.er_diagram.circular.entities import BaseEntity

    diagram = BaseEntity.get_diagram()
    user_cfg = next((c for c in diagram.configs if c.kls == UserEntity), None)

    # UserEntity should have list[PostEntity] relationship
    assert user_cfg is not None
    assert len(user_cfg.relationships) == 1
    rel = user_cfg.relationships[0]

    # Verify it's a list type with correct target
    assert rel.target_kls == list[PostEntity]
    assert rel.target_kls.__origin__ == list
    assert rel.target_kls.__args__[0] == PostEntity


def test_module_path_syntax_with_simple_class():
    """
    Test that module path syntax works with simple class reference.
    """
    from tests.er_diagram.circular.entities.user import UserEntity
    from tests.er_diagram.circular.entities.post import PostEntity
    from tests.er_diagram.circular.entities import BaseEntity

    diagram = BaseEntity.get_diagram()
    post_cfg = next((c for c in diagram.configs if c.kls == PostEntity), None)

    # PostEntity should have UserEntity relationship
    assert post_cfg is not None
    assert len(post_cfg.relationships) == 1
    rel = post_cfg.relationships[0]

    # Verify it's the UserEntity class (not a string)
    assert rel.target_kls == UserEntity
    assert isinstance(rel.target_kls, type)
    assert rel.target_kls.__name__ == 'UserEntity'