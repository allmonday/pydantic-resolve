from typing import get_origin
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
    assert user_rel.fk == 'id'
    # Should be resolved to list[PostEntity], not a string
    assert user_rel.target == list[PostEntity]

    # Verify PostEntity has a relationship to UserEntity
    assert len(post_cfg.relationships) == 1
    post_rel = post_cfg.relationships[0]
    assert post_rel.fk == 'user_id'
    # Should be resolved to UserEntity, not a string
    assert post_rel.target == UserEntity


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
    assert rel.target == list[PostEntity]
    assert get_origin(rel.target) is list
    assert rel.target.__args__[0] == PostEntity


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
    assert rel.target == UserEntity
    assert isinstance(rel.target, type)
    assert rel.target.__name__ == 'UserEntity'


def test_create_auto_load_with_circular_module_path_references():
    """
    Test that diagram.create_auto_load() does not introduce extra circular-import
    problems when the ERD itself uses module-path string targets.

    This also verifies that DefineSubset can consume the diagram-bound AutoLoad
    metadata and auto-inject missing FK fields from both sides of a circular
    entity relationship.
    """
    from typing import Annotated, Optional

    from pydantic_resolve import DefineSubset
    from pydantic_resolve.utils.er_diagram import LoaderInfo
    from tests.er_diagram.circular.entities.user import UserEntity
    from tests.er_diagram.circular.entities.post import PostEntity
    from tests.er_diagram.circular.entities import BaseEntity

    diagram = BaseEntity.get_diagram()
    AutoLoad = diagram.create_auto_load()

    class UserSubset(DefineSubset):
        __subset__ = (UserEntity, ['name'])

        posts: Annotated[list[PostEntity], AutoLoad()] = []

    class PostSubset(DefineSubset):
        __subset__ = (PostEntity, ['id'])

        user: Annotated[Optional[UserEntity], AutoLoad()] = None

    user_meta = next(
        meta for meta in UserSubset.model_fields['posts'].metadata if isinstance(meta, LoaderInfo)
    )
    post_meta = next(
        meta for meta in PostSubset.model_fields['user'].metadata if isinstance(meta, LoaderInfo)
    )

    assert user_meta._er_configs_map is not None
    assert user_meta._er_configs_map is post_meta._er_configs_map
    assert set(user_meta._er_configs_map.keys()) == {UserEntity, PostEntity}

    # UserSubset omits id, but posts relationship needs fk='id'.
    assert 'id' in UserSubset.model_fields
    assert UserSubset.model_fields['id'].exclude is True

    # PostSubset omits user_id, but user relationship needs fk='user_id'.
    assert 'user_id' in PostSubset.model_fields
    assert PostSubset.model_fields['user_id'].exclude is True