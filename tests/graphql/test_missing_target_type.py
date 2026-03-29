"""
Tests for verifying GraphQL introspection behavior when Relationship.target_kls
is not in the ErDiagram entity list.

This test file verifies:
1. Whether IntrospectionGenerator correctly collects types from Relationship.target_kls
2. Whether SDLBuilder correctly generates type definitions for target_kls
3. Consistency between IntrospectionGenerator and SDLBuilder type lists
4. Both ErDiagram manual config and base_entity() + __relationships__ patterns
"""

from pydantic import BaseModel
from typing import Optional, List

from pydantic_resolve import (
    base_entity,
    Relationship,
    Entity,
    ErDiagram,
    query,
)
from pydantic_resolve.graphql.schema.generators.sdl_builder import SDLBuilder
from pydantic_resolve.graphql.schema.generators.introspection_generator import IntrospectionGenerator


# ============================================================================
# Test 1: ErDiagram manual config - target_kls not in configs list
# ============================================================================

class ProfileInfo(BaseModel):
    """Profile type - NOT registered as Entity in ErDiagram"""
    bio: str
    avatar_url: Optional[str] = None


class AddressInfo(BaseModel):
    """Address type - also NOT registered, used to test nested types"""
    street: str
    city: str


class ContactInfo(BaseModel):
    """Contact type with nested AddressInfo"""
    email: str
    address: AddressInfo


class UserEntityForManualConfig(BaseModel):
    """User entity - will be registered in ErDiagram"""
    id: int
    name: str
    profile_id: int


class PostEntityForManualConfig(BaseModel):
    """Post entity - will be registered in ErDiagram"""
    id: int
    title: str
    author_id: int


class TestErDiagramMissingTargetType:
    """Test ErDiagram config where target_kls is not in configs list"""

    def test_introspection_includes_target_kls_type(self):
        """
        Verify that IntrospectionGenerator correctly collects target_kls types.

        Setup:
        - ProfileInfo is NOT registered in ErDiagram
        - UserEntity's Relationship references ProfileInfo as target_kls
        - Check if introspection's types list includes ProfileInfo
        """
        diagram = ErDiagram(configs=[
            Entity(
                kls=UserEntityForManualConfig,
                relationships=[
                    Relationship(
                        field='profile_id',
                        target_kls=ProfileInfo,
                        field_name='profile'
                    )
                ]
            )
        ])

        # Create IntrospectionGenerator
        generator = IntrospectionGenerator(diagram)
        introspection_data = generator.generate()

        # Extract type names from introspection
        type_names = {t['name'] for t in introspection_data['types']}

        # ProfileInfo should be included in types list
        assert 'ProfileInfo' in type_names, \
            f"ProfileInfo not found in introspection types: {type_names}"

        # UserEntityForManualConfig should also be present
        assert 'UserEntityForManualConfig' in type_names

    def test_sdl_builder_includes_target_kls_type(self):
        """
        Verify that SDLBuilder correctly generates type definitions for target_kls.
        """
        diagram = ErDiagram(configs=[
            Entity(
                kls=UserEntityForManualConfig,
                relationships=[
                    Relationship(
                        field='profile_id',
                        target_kls=ProfileInfo,
                        field_name='profile',
                        loader=lambda x: []  # Required for field to appear in SDL
                    )
                ]
            )
        ])

        builder = SDLBuilder(diagram)
        sdl = builder.generate()

        # SDL should include ProfileInfo type definition
        assert 'type ProfileInfo' in sdl, \
            f"ProfileInfo type not found in SDL:\n{sdl}"

        # SDL should include the relationship field
        assert 'profile: ProfileInfo!' in sdl or 'profile: ProfileInfo' in sdl

    def test_introspection_includes_nested_types_from_target_kls(self):
        """
        Verify that nested types within target_kls are also collected.

        Setup:
        - ContactInfo is NOT registered in ErDiagram
        - ContactInfo contains nested AddressInfo
        - UserEntity's Relationship references ContactInfo
        - Both ContactInfo and AddressInfo should be in types list
        """
        diagram = ErDiagram(configs=[
            Entity(
                kls=UserEntityForManualConfig,
                relationships=[
                    Relationship(
                        field='id',  # Using id as a dummy field
                        target_kls=ContactInfo,
                        field_name='contact',
                        loader=lambda x: []  # Required for field to appear in introspection
                    )
                ]
            )
        ])

        generator = IntrospectionGenerator(diagram)
        introspection_data = generator.generate()
        type_names = {t['name'] for t in introspection_data['types']}

        # Both ContactInfo and nested AddressInfo should be present
        assert 'ContactInfo' in type_names, \
            f"ContactInfo not found in types: {type_names}"
        assert 'AddressInfo' in type_names, \
            f"AddressInfo not found in types: {type_names}"

    def test_introspection_field_references_valid_type(self):
        """
        Verify that introspection field type references point to defined types.

        If a field's type references "ProfileInfo", then "ProfileInfo" must
        be defined in the types list.
        """
        diagram = ErDiagram(configs=[
            Entity(
                kls=UserEntityForManualConfig,
                relationships=[
                    Relationship(
                        field='profile_id',
                        target_kls=ProfileInfo,
                        field_name='profile',
                        loader=lambda x: []  # Required for field to appear in introspection
                    )
                ]
            )
        ])

        generator = IntrospectionGenerator(diagram)
        introspection_data = generator.generate()

        # Get all defined type names
        type_names = {t['name'] for t in introspection_data['types']}

        # Find UserEntityForManualConfig type definition
        user_type = None
        for t in introspection_data['types']:
            if t['name'] == 'UserEntityForManualConfig':
                user_type = t
                break

        assert user_type is not None, "UserEntityForManualConfig not found in types"

        # Check that all field type references are valid
        for field in user_type.get('fields', []):
            field_type = field.get('type', {})
            self._verify_type_reference_valid(field_type, type_names)

    def _verify_type_reference_valid(self, type_ref: dict, valid_types: set):
        """Recursively verify that type references point to valid types."""
        if type_ref.get('name'):
            type_name = type_ref['name']
            # Skip scalar types
            if type_name not in ('Int', 'Float', 'String', 'Boolean', 'ID'):
                assert type_name in valid_types, \
                    f"Type '{type_name}' is referenced but not defined in types list"

        # Check nested type (LIST, NON_NULL)
        if type_ref.get('ofType'):
            self._verify_type_reference_valid(type_ref['ofType'], valid_types)


# ============================================================================
# Test 2: base_entity() + __relationships__ configuration
# ============================================================================

class TestBaseEntityRelationships:
    """Test base_entity() configuration with __relationships__"""

    def test_get_diagram_collects_all_entities(self):
        """
        Verify that get_diagram() correctly collects all entities
        that inherit from Base.

        Setup:
        - Create BaseEntity using base_entity()
        - UserEntity and ProfileEntity both inherit from Base
        - UserEntity.__relationships__ references ProfileEntity
        - Both should be in get_diagram().configs
        """
        BaseEntity = base_entity()

        class ProfileEntityTest(BaseModel, BaseEntity):
            __relationships__ = []
            id: int
            bio: str

        class UserEntityTest(BaseModel, BaseEntity):
            __relationships__ = [
                Relationship(
                    field='profile_id',
                    target_kls=ProfileEntityTest,
                    field_name='profile'
                )
            ]
            id: int
            name: str
            profile_id: int

        diagram = BaseEntity.get_diagram()
        config_class_names = {cfg.kls.__name__ for cfg in diagram.configs}

        # Both entities should be collected
        assert 'UserEntityTest' in config_class_names, \
            f"UserEntityTest not in diagram configs: {config_class_names}"
        assert 'ProfileEntityTest' in config_class_names, \
            f"ProfileEntityTest not in diagram configs: {config_class_names}"

    def test_introspection_with_base_entity_config(self):
        """
        Verify introspection works correctly with base_entity() configuration.
        """
        BaseEntity = base_entity()

        class ProfileForIntrospection(BaseModel, BaseEntity):
            __relationships__ = []
            id: int
            bio: str

        class UserForIntrospection(BaseModel, BaseEntity):
            __relationships__ = [
                Relationship(
                    field='profile_id',
                    target_kls=ProfileForIntrospection,
                    field_name='profile'
                )
            ]
            id: int
            name: str
            profile_id: int

            @query
            @staticmethod
            async def get_all() -> List['UserForIntrospection']:
                return []

        diagram = BaseEntity.get_diagram()
        generator = IntrospectionGenerator(diagram, query_map={})
        introspection_data = generator.generate()

        type_names = {t['name'] for t in introspection_data['types']}

        # Both entities should be in introspection types
        assert 'UserForIntrospection' in type_names
        assert 'ProfileForIntrospection' in type_names


# ============================================================================
# Test 3: IntrospectionGenerator vs SDLBuilder consistency
# ============================================================================

class TestIntrospectionSDLConsistency:
    """Verify consistency between IntrospectionGenerator and SDLBuilder"""

    def test_type_lists_match_for_missing_target_kls(self):
        """
        Compare type lists generated by SDLBuilder and IntrospectionGenerator.

        When target_kls is not in configs, both should handle it consistently.
        """
        diagram = ErDiagram(configs=[
            Entity(
                kls=UserEntityForManualConfig,
                relationships=[
                    Relationship(
                        field='profile_id',
                        target_kls=ProfileInfo,
                        field_name='profile'
                    )
                ]
            )
        ])

        # Generate SDL
        sdl_builder = SDLBuilder(diagram)
        sdl = sdl_builder.generate()

        # Generate introspection
        introspection_generator = IntrospectionGenerator(diagram)
        introspection = introspection_generator.generate()

        # Extract type names from both
        sdl_types = self._extract_type_names_from_sdl(sdl)
        introspection_types = {t['name'] for t in introspection['types']}

        # Both should include ProfileInfo
        assert 'ProfileInfo' in sdl_types, \
            f"ProfileInfo not in SDL types: {sdl_types}"
        assert 'ProfileInfo' in introspection_types, \
            f"ProfileInfo not in introspection types: {introspection_types}"

        # Both should include UserEntityForManualConfig
        assert 'UserEntityForManualConfig' in sdl_types
        assert 'UserEntityForManualConfig' in introspection_types

    def test_nested_types_consistency(self):
        """
        Verify nested types are collected consistently.
        """
        diagram = ErDiagram(configs=[
            Entity(
                kls=UserEntityForManualConfig,
                relationships=[
                    Relationship(
                        field='id',
                        target_kls=ContactInfo,  # Contains nested AddressInfo
                        field_name='contact'
                    )
                ]
            )
        ])

        # Generate both
        sdl_builder = SDLBuilder(diagram)
        sdl = sdl_builder.generate()

        introspection_generator = IntrospectionGenerator(diagram)
        introspection = introspection_generator.generate()

        sdl_types = self._extract_type_names_from_sdl(sdl)
        introspection_types = {t['name'] for t in introspection['types']}

        # Both should include ContactInfo and AddressInfo
        for expected_type in ['ContactInfo', 'AddressInfo']:
            sdl_has = expected_type in sdl_types
            intro_has = expected_type in introspection_types

            # Both should have the same result (both true or both false)
            assert sdl_has == intro_has, \
                f"Inconsistency for {expected_type}: SDL has it ({sdl_has}), Introspection has it ({intro_has})"

    def _extract_type_names_from_sdl(self, sdl: str) -> set:
        """Extract type names from SDL string."""
        import re
        # Match "type TypeName {" patterns
        pattern = r'type\s+(\w+)\s*\{'
        return set(re.findall(pattern, sdl))


# ============================================================================
# Test 4: Edge cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases for missing target types"""

    def test_list_target_kls_not_registered(self):
        """
        Test that list[TargetType] where TargetType is not registered works.
        """
        diagram = ErDiagram(configs=[
            Entity(
                kls=UserEntityForManualConfig,
                relationships=[
                    Relationship(
                        field='id',
                        target_kls=list[PostEntityForManualConfig],
                        field_name='posts'
                    )
                ]
            )
        ])

        # Both should handle list[PostEntityForManualConfig]
        sdl_builder = SDLBuilder(diagram)
        sdl = sdl_builder.generate()
        assert 'type PostEntityForManualConfig' in sdl

        introspection_generator = IntrospectionGenerator(diagram)
        introspection = introspection_generator.generate()
        type_names = {t['name'] for t in introspection['types']}
        assert 'PostEntityForManualConfig' in type_names

    def test_multiple_relationships_same_target(self):
        """
        Test multiple relationships referencing the same unregistered type.
        """
        diagram = ErDiagram(configs=[
            Entity(
                kls=UserEntityForManualConfig,
                relationships=[
                    Relationship(
                        field='profile_id',
                        target_kls=ProfileInfo,
                        field_name='profile'
                    ),
                    Relationship(
                        field='id',
                        target_kls=list[ProfileInfo],  # Same type but as list
                        field_name='profiles'
                    )
                ]
            )
        ])

        introspection_generator = IntrospectionGenerator(diagram)
        introspection = introspection_generator.generate()

        # ProfileInfo should appear only once
        profile_count = sum(1 for t in introspection['types'] if t['name'] == 'ProfileInfo')
        assert profile_count == 1, \
            f"ProfileInfo should appear exactly once, but appeared {profile_count} times"
