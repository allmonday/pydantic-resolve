"""
Unit tests for ResponseBuilder model caching functionality.
"""

import pytest
from pydantic import BaseModel

from pydantic_resolve import base_entity
from pydantic_resolve.graphql.types import FieldSelection
from pydantic_resolve.graphql.response_builder import ResponseBuilder


class TestFieldSelectionHashable:
    """Tests for FieldSelection hashability."""

    def test_simple_field_selection_hash(self):
        """Simple field selection should be hashable."""
        fs = FieldSelection(alias=None, sub_fields=None, arguments={'id': 1})
        # Should not raise
        hash(fs)

    def test_field_selection_equality(self):
        """FieldSelection with same alias/sub_fields should be equal (arguments excluded from comparison)."""
        fs1 = FieldSelection(
            alias=None,
            sub_fields={'name': FieldSelection(), 'id': FieldSelection()},
            arguments={'id': 1}
        )
        fs2 = FieldSelection(
            alias=None,
            sub_fields={'name': FieldSelection(), 'id': FieldSelection()},
            arguments={'id': 999}  # Different arguments
        )
        assert fs1 == fs2
        assert hash(fs1) == hash(fs2)

    def test_field_selection_inequality(self):
        """FieldSelection with different alias/sub_fields should not be equal."""
        fs1 = FieldSelection(alias='alias1')
        fs2 = FieldSelection(alias='alias2')
        assert fs1 != fs2
        assert hash(fs1) != hash(fs2)

    def test_nested_field_selection_hash(self):
        """Nested field selections should be hashable."""
        fs = FieldSelection(
            sub_fields={
                'user': FieldSelection(
                    sub_fields={
                        'posts': FieldSelection(
                            sub_fields={'title': FieldSelection()}
                        )
                    }
                )
            }
        )
        # Should not raise
        hash(fs)


class TestResponseBuilderCache:
    """Tests for ResponseBuilder caching."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        BaseEntity = base_entity()

        class UserEntity(BaseModel, BaseEntity):
            __relationships__ = []
            id: int
            name: str
            email: str

        class PostEntity(BaseModel, BaseEntity):
            __relationships__ = []
            id: int
            title: str
            user_id: int

        self.er_diagram = BaseEntity.get_diagram()
        self.builder = ResponseBuilder(self.er_diagram)
        self.UserEntity = UserEntity
        self.PostEntity = PostEntity

    def test_cache_hit_same_structure_different_args(self):
        """Same query structure, different arguments should hit cache."""
        fs1 = FieldSelection(
            sub_fields={'name': FieldSelection(), 'id': FieldSelection()},
            arguments={'id': 1}
        )
        fs2 = FieldSelection(
            sub_fields={'name': FieldSelection(), 'id': FieldSelection()},
            arguments={'id': 2}
        )

        model1 = self.builder.build_response_model(self.UserEntity, fs1)
        model2 = self.builder.build_response_model(self.UserEntity, fs2)

        assert model1 is model2

        # Verify cache stats
        info = self.builder._build_cached.cache_info()
        assert info.hits == 1  # First call was a hit
        assert info.misses == 1  # First call was a miss

    def test_cache_miss_different_structure(self):
        """Different query structure should miss cache."""
        fs1 = FieldSelection(sub_fields={'name': FieldSelection()})
        fs2 = FieldSelection(sub_fields={'email': FieldSelection()})

        model1 = self.builder.build_response_model(self.UserEntity, fs1)
        model2 = self.builder.build_response_model(self.UserEntity, fs2)

        # Should return different class objects
        assert model1 is not model2
        # Verify cache stats
        info = self.builder._build_cached.cache_info()
        assert info.hits == 0
        assert info.misses == 2

    def test_cache_nested_models(self):
        """Nested models should also be cached."""
        fs1 = FieldSelection(
            sub_fields={
                'name': FieldSelection(),
            },
            arguments={'id': 1}
        )
        fs2 = FieldSelection(
            sub_fields={
                'name': FieldSelection(),
            },
            arguments={'id': 2}
        )

        model1 = self.builder.build_response_model(self.UserEntity, fs1)
        model2 = self.builder.build_response_model(self.UserEntity, fs2)

        assert model1 is model2

        # Verify cache stats
        info = self.builder._build_cached.cache_info()
        assert info.hits == 1  # First call was a hit
        assert info.misses == 1  # First call was a miss

    def test_different_entities_different_cache(self):
        """Same field selection for different entities should not share cache."""
        fs = FieldSelection(sub_fields={'id': FieldSelection(), 'name': FieldSelection()})

        model1 = self.builder.build_response_model(self.UserEntity, fs)
        model2 = self.builder.build_response_model(self.PostEntity, fs)

        # Should return different class objects
        assert model1 is not model2
