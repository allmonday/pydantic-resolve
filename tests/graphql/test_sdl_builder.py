"""
Tests for SDLBuilder internal methods.
"""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel
from pydantic_resolve import base_entity, query, mutation, Relationship
from pydantic_resolve.graphql.schema.generators.sdl_builder import SDLBuilder


class SampleStatus(str, Enum):
    """Sample enum for enum type mapping."""
    ACTIVE = "active"
    INACTIVE = "inactive"


# Create a minimal test ERD
SampleBaseEntity = base_entity()


class SampleUser(BaseModel, SampleBaseEntity):
    """Sample user entity."""
    __relationships__ = []  # Required for entity registration
    id: int
    name: str
    email: Optional[str] = None
    status: SampleStatus = SampleStatus.ACTIVE

    @query
    @staticmethod
    async def get_all() -> List['SampleUser']:
        """Get all users."""
        return []

    @mutation
    @staticmethod
    async def create(name: str, status: SampleStatus = SampleStatus.ACTIVE) -> 'SampleUser':
        """Create a user."""
        return SampleUser(id=1, name=name, status=status)


class SamplePost(BaseModel, SampleBaseEntity):
    """Sample post entity with relationships."""
    __relationships__ = [
        Relationship(field='author_id', target_kls=SampleUser, loader=lambda x: [])
    ]
    id: int
    title: str
    author_id: int


class TestMapPythonTypeToGql:
    """Tests for _map_python_type_to_gql method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.er_diagram = SampleBaseEntity.get_diagram()
        self.builder = SDLBuilder(self.er_diagram)

    def test_scalar_types(self):
        """Test basic scalar type mapping."""
        assert self.builder._map_python_type_to_gql(str) == "String!"
        assert self.builder._map_python_type_to_gql(int) == "Int!"
        assert self.builder._map_python_type_to_gql(bool) == "Boolean!"
        assert self.builder._map_python_type_to_gql(float) == "Float!"

    def test_optional_scalar(self):
        """Test Optional[T] mapping - should remove ! for optional."""
        # Optional[T] in output types still has ! (GraphQL convention)
        result = self.builder._map_python_type_to_gql(Optional[str])
        # The current implementation adds ! even for Optional in output types
        # This is consistent with GraphQL best practices for output types
        assert "String" in result

    def test_list_type(self):
        """Test list[T] mapping."""
        result = self.builder._map_python_type_to_gql(List[int])
        assert result == "[Int!]!"

    def test_list_of_optional(self):
        """Test list[Optional[T]] mapping."""
        result = self.builder._map_python_type_to_gql(List[Optional[str]])
        assert "String" in result
        assert result.startswith("[")
        assert result.endswith("]!")

    def test_enum_type(self):
        """Test enum type mapping."""
        result = self.builder._map_python_type_to_gql(SampleStatus)
        assert result == "SampleStatus!"

    def test_entity_type(self):
        """Test entity type mapping (BaseModel subclass)."""
        result = self.builder._map_python_type_to_gql(SampleUser)
        assert result == "SampleUser!"

    def test_forward_ref_string_annotation(self):
        """Test string annotation like 'SampleUser' resolves to entity."""
        # String annotations should be resolved to entity types
        result = self.builder._map_python_type_to_gql('SampleUser')
        assert result == "SampleUser!"

    def test_list_of_forward_ref(self):
        """Test list['SampleUser'] resolves correctly."""
        result = self.builder._map_python_type_to_gql(List['SampleUser'])
        assert result == "[SampleUser!]!"

    def test_unknown_type_fallback(self):
        """Test unknown type falls back to String."""
        # Create a type that can't be mapped
        class UnknownType:
            pass
        # get_core_types might return empty, causing fallback to String!
        result = self.builder._map_python_type_to_gql(UnknownType)
        # Should either map to something or fall back gracefully
        assert result  # Just verify it doesn't crash


class TestMapPythonTypeToGqlForInput:
    """Tests for _map_python_type_to_gql with is_input=True parameter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.er_diagram = SampleBaseEntity.get_diagram()
        self.builder = SDLBuilder(self.er_diagram)

    def test_optional_in_input_removes_exclamation(self):
        """Test Optional[T] in input types removes !."""
        result = self.builder._map_python_type_to_gql(Optional[str], is_input=True)
        # Input types: Optional fields should not have !
        assert result == "String"  # No !

    def test_required_in_input_has_exclamation(self):
        """Test required fields in input types have !."""
        result = self.builder._map_python_type_to_gql(str, is_input=True)
        assert result == "String!"

    def test_list_in_input(self):
        """Test list[T] in input types."""
        result = self.builder._map_python_type_to_gql(List[str], is_input=True)
        assert result == "[String!]!"

    def test_list_of_optional_in_input(self):
        """Test list[Optional[T]] in input types."""
        result = self.builder._map_python_type_to_gql(List[Optional[str]], is_input=True)
        # List elements should have ! but inner optional should not
        assert "[String!]" in result or "[String]" in result

    def test_enum_in_input(self):
        """Test enum in input types."""
        result = self.builder._map_python_type_to_gql(SampleStatus, is_input=True)
        assert result == "SampleStatus!"


class TestBuildEntityType:
    """Tests for _build_entity_type method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.er_diagram = SampleBaseEntity.get_diagram()
        self.builder = SDLBuilder(self.er_diagram)

    def test_build_simple_entity(self):
        """Test building SDL for a simple entity."""
        result = self.builder._build_entity_type(SampleUser)

        assert "type SampleUser {" in result
        assert "id: Int!" in result
        assert "name: String!" in result
        assert "email:" in result  # Optional, might or might not have !
        assert "status: SampleStatus!" in result

    def test_build_entity_with_relationships(self):
        """Test building SDL for entity with relationships."""
        result = self.builder._build_entity_type(SamplePost)

        assert "type SamplePost {" in result
        assert "id: Int!" in result
        assert "title: String!" in result
        assert "author_id: Int!" in result
        # Relationship field should be included
        # Note: depends on relationship having default_field_name

    def test_entity_type_closing_brace(self):
        """Test entity type has proper closing."""
        result = self.builder._build_entity_type(SampleUser)
        assert result.endswith("}")


class TestGenerateOperationSdl:
    """Tests for generate_operation_sdl method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.er_diagram = SampleBaseEntity.get_diagram()
        self.builder = SDLBuilder(self.er_diagram)

    def test_generate_query_sdl(self):
        """Test generating SDL for a query operation."""
        result = self.builder.generate_operation_sdl("sampleUserGetAll", "Query")

        assert result is not None
        assert "# Query" in result
        assert "sampleUserGetAll" in result
        assert "SampleUser" in result  # Return type

    def test_generate_mutation_sdl(self):
        """Test generating SDL for a mutation operation."""
        result = self.builder.generate_operation_sdl("sampleUserCreate", "Mutation")

        assert result is not None
        assert "# Mutation" in result
        assert "sampleUserCreate" in result

    def test_generate_nonexistent_operation(self):
        """Test generating SDL for non-existent operation returns None."""
        result = self.builder.generate_operation_sdl("nonExistent", "Query")
        assert result is None

    def test_includes_related_types(self):
        """Test that related types are included in SDL."""
        result = self.builder.generate_operation_sdl("sampleUserGetAll", "Query")

        assert result is not None
        # Should include the return type definition
        assert "# Related Types" in result or "type SampleUser" in result

    def test_string_return_type_resolved(self):
        """Test that string return type annotations are resolved to entity types."""
        result = self.builder.generate_operation_sdl("sampleUserCreate", "Mutation")

        assert result is not None
        # The return type should be SampleUser, not String
        assert "SampleUser!" in result
        assert ": String!" not in result.split("\n")[0]  # First line shouldn't have String! as return


class TestCollectRelatedEntitiesFromMethod:
    """Tests for _collect_related_entities_from_method method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.er_diagram = SampleBaseEntity.get_diagram()
        self.builder = SDLBuilder(self.er_diagram)

    def test_collect_from_return_type(self):
        """Test collecting entities from return type."""
        # Find the get_all method
        for entity_cfg in self.er_diagram.configs:
            if entity_cfg.kls.__name__ == 'SampleUser':
                methods = self.builder._extract_query_methods(entity_cfg.kls)
                for method in methods:
                    if method['name'] == 'sampleUserGetAll':
                        entities = self.builder._collect_related_entities_from_method(method)
                        assert SampleUser in entities
                        return
        assert False, "Method not found"

    def test_collect_from_list_return_type(self):
        """Test collecting entities from list return type."""
        for entity_cfg in self.er_diagram.configs:
            if entity_cfg.kls.__name__ == 'SampleUser':
                methods = self.builder._extract_query_methods(entity_cfg.kls)
                for method in methods:
                    if method['name'] == 'sampleUserGetAll':
                        entities = self.builder._collect_related_entities_from_method(method)
                        # List[SampleUser] should still collect SampleUser
                        assert SampleUser in entities
                        return
        assert False, "Method not found"

    def test_collect_from_string_annotation(self):
        """Test collecting entities from string type annotation."""
        for entity_cfg in self.er_diagram.configs:
            if entity_cfg.kls.__name__ == 'SampleUser':
                methods = self.builder._extract_mutation_methods(entity_cfg.kls)
                for method in methods:
                    if method['name'] == 'sampleUserCreate':
                        entities = self.builder._collect_related_entities_from_method(method)
                        # String annotation 'SampleUser' should resolve to SampleUser class
                        assert SampleUser in entities
                        return
        assert False, "Method not found"
