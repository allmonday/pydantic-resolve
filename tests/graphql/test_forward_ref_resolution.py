"""
Tests for forward reference resolution in __relationships__.

This test file verifies that string type references in __relationships__
are correctly resolved by _resolve_ref function in base_entity().

Classes are defined at module level (global scope) so that _resolve_ref
can find them via sys.modules[module_name].
"""

from pydantic import BaseModel

from pydantic_resolve import (
    base_entity,
    Relationship,
)


# Define entities at module level (global scope)
# This is required for _resolve_ref to work correctly

BaseEntityForForwardRef = base_entity()


class ProfileEntityForwardRef(BaseModel, BaseEntityForForwardRef):
    """Profile entity for forward reference test."""
    __relationships__ = []
    id: int
    bio: str


class UserEntityForwardRef(BaseModel, BaseEntityForForwardRef):
    """User entity with string reference to ProfileEntityForwardRef."""
    __relationships__ = [
        Relationship(
            fk='profile_id',
            target='ProfileEntityForwardRef',  # String reference
            name='profile'
        )
    ]
    id: int
    name: str
    profile_id: int


class TestForwardRefResolution:
    """Test forward reference resolution in __relationships__"""

    def test_forward_ref_resolution_in_relationships(self):
        """
        Verify that string type references in __relationships__ are resolved correctly.
        """
        diagram = BaseEntityForForwardRef.get_diagram()

        # Verify that the relationship target_kls is resolved to the actual class
        user_config = None
        for cfg in diagram.entities:
            if cfg.kls.__name__ == 'UserEntityForwardRef':
                user_config = cfg
                break

        assert user_config is not None, "UserEntityForwardRef config not found"
        assert len(user_config.relationships) == 1

        rel = user_config.relationships[0]
        # After resolution, target should be the actual class, not a string
        assert rel.target == ProfileEntityForwardRef, \
            f"Expected target to be ProfileEntityForwardRef, got {rel.target}"
