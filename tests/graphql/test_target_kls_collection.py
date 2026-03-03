"""
Test that Relationship.target_kls types are collected and generated in GraphQL schema.
"""

from typing import List
from pydantic import BaseModel
from pydantic_resolve import Relationship, Entity, ErDiagram, MultipleRelationship, Link
from pydantic_resolve.graphql import SchemaBuilder


# Define Pydantic models (NOT registered in ErDiagram)
class AddressInfo(BaseModel):
    """Address type - NOT registered as Entity"""
    street: str
    city: str
    zip_code: str


class ProfileInfo(BaseModel):
    """Profile type - NOT registered as Entity, has nested AddressInfo"""
    bio: str
    address: AddressInfo


# Define Entity with Relationship to unregistered types
class UserEntity(BaseModel):
    """User entity - registered in ErDiagram"""
    id: int
    name: str
    profile_id: int


class PostEntity(BaseModel):
    """Post entity - registered in ErDiagram"""
    id: int
    title: str
    author_id: int


class CommentEntity(BaseModel):
    """Comment entity - for testing MultipleRelationship"""
    id: int
    text: str


class TestTargetKlsCollection:
    """Test that target_kls types are collected for schema generation"""

    def test_relationship_target_kls_collected(self):
        """Test that Relationship.target_kls type is collected even if not registered"""
        diagram = ErDiagram(configs=[
            Entity(
                kls=UserEntity,
                relationships=[
                    Relationship(
                        field='profile_id',
                        target_kls=ProfileInfo,  # Not registered!
                        default_field_name='profile'
                    )
                ]
            )
        ])

        builder = SchemaBuilder(diagram)
        schema = builder.build_schema()

        # Verify ProfileInfo type is generated
        assert 'type ProfileInfo' in schema
        # Verify nested AddressInfo is also generated (recursive collection)
        assert 'type AddressInfo' in schema

    def test_list_target_kls_collected(self):
        """Test that list[TargetType] is correctly extracted"""
        diagram = ErDiagram(configs=[
            Entity(
                kls=UserEntity,
                relationships=[
                    Relationship(
                        field='id',
                        target_kls=list[PostEntity],  # Not registered!
                        default_field_name='posts'
                    )
                ]
            )
        ])

        builder = SchemaBuilder(diagram)
        schema = builder.build_schema()

        # Verify PostEntity type is generated
        assert 'type PostEntity' in schema

    def test_registered_entity_not_duplicated(self):
        """Test that already registered entities are not duplicated"""
        diagram = ErDiagram(configs=[
            Entity(kls=UserEntity, relationships=[]),
            Entity(
                kls=PostEntity,
                relationships=[
                    Relationship(
                        field='author_id',
                        target_kls=UserEntity,  # Already registered
                        default_field_name='author'
                    )
                ]
            )
        ])

        builder = SchemaBuilder(diagram)
        schema = builder.build_schema()

        # Count UserEntity occurrences (should be exactly 1)
        assert schema.count('type UserEntity') == 1

    def test_multiple_relationship_target_kls_collected(self):
        """Test that MultipleRelationship.target_kls type is also collected"""
        diagram = ErDiagram(configs=[
            Entity(
                kls=PostEntity,
                relationships=[
                    MultipleRelationship(
                        field='id',
                        target_kls=list[CommentEntity],  # Not registered!
                        links=[
                            Link(biz='comments', default_field_name='comments')
                        ]
                    )
                ]
            )
        ])

        builder = SchemaBuilder(diagram)
        schema = builder.build_schema()

        # Verify CommentEntity type is generated
        assert 'type CommentEntity' in schema
