"""Tests for GraphQL enum support."""
import pytest
from typing import Optional, List
from pydantic import BaseModel

from pydantic_resolve import config_global_resolver
from pydantic_resolve.graphql import GraphQLHandler, SchemaBuilder
from tests.graphql.fixtures.enum_entities import (
    BaseEntity,
    UserRole,
    PostStatus,
    Priority,
)


class TestEnumTypeMapping:
    """Test enum type mapping functions."""

    def test_is_enum_type(self):
        """Test enum type detection."""
        from pydantic_resolve.graphql.type_mapping import is_enum_type

        assert is_enum_type(UserRole) is True
        assert is_enum_type(PostStatus) is True
        assert is_enum_type(Priority) is True  # IntEnum
        assert is_enum_type(str) is False
        assert is_enum_type(int) is False
        assert is_enum_type(BaseModel) is False

    def test_get_enum_values(self):
        """Test getting enum values."""
        from pydantic_resolve.graphql.type_mapping import get_enum_names

        assert get_enum_names(UserRole) == ["ADMIN", "USER", "GUEST"]
        assert get_enum_names(PostStatus) == ["DRAFT", "PUBLISHED", "ARCHIVED"]
        assert get_enum_names(Priority) == ["LOW", "MEDIUM", "HIGH"]

    def test_get_enum_values_non_enum(self):
        """Test get_enum_values with non-enum type returns empty list."""
        from pydantic_resolve.graphql.type_mapping import get_enum_names

        assert get_enum_names(str) == []
        assert get_enum_names(int) == []

    def test_map_scalar_type_with_enum(self):
        """Test map_scalar_type returns enum name for enum types."""
        from pydantic_resolve.graphql.type_mapping import map_scalar_type

        assert map_scalar_type(UserRole) == "UserRole"
        assert map_scalar_type(PostStatus) == "PostStatus"
        assert map_scalar_type(Priority) == "Priority"

    def test_map_python_to_graphql_with_enum(self):
        """Test map_python_to_graphql handles enum types."""
        from pydantic_resolve.graphql.type_mapping import map_python_to_graphql

        assert map_python_to_graphql(UserRole) == "UserRole!"
        assert map_python_to_graphql(Optional[UserRole]) == "UserRole"
        assert map_python_to_graphql(List[UserRole]) == "[UserRole!]!"


class TestEnumSDLGeneration:
    """Test enum SDL generation."""

    def setup_method(self):
        """Set up test environment."""
        self.er_diagram = BaseEntity.get_diagram()
        config_global_resolver(self.er_diagram)

    def test_enum_in_schema(self):
        """Test that enums appear in generated schema."""
        schema_builder = SchemaBuilder(self.er_diagram)
        sdl = schema_builder.build_schema()

        # Check enum definition exists
        assert "enum UserRole" in sdl
        assert "ADMIN" in sdl
        assert "USER" in sdl
        assert "GUEST" in sdl

    def test_enum_field_type(self):
        """Test that enum fields have correct type in schema."""
        schema_builder = SchemaBuilder(self.er_diagram)
        sdl = schema_builder.build_schema()

        # Check field type is enum, not String
        assert "role: UserRole!" in sdl

    def test_multiple_enums_in_schema(self):
        """Test multiple enum types in schema."""
        schema_builder = SchemaBuilder(self.er_diagram)
        sdl = schema_builder.build_schema()

        # Both enums should be defined
        assert "enum UserRole" in sdl
        assert "enum PostStatus" in sdl
        assert "DRAFT" in sdl
        assert "PUBLISHED" in sdl


class TestEnumIntrospection:
    """Test enum introspection."""

    def setup_method(self):
        """Set up test environment."""
        self.er_diagram = BaseEntity.get_diagram()
        config_global_resolver(self.er_diagram)
        self.handler = GraphQLHandler(self.er_diagram)

    @pytest.mark.asyncio
    async def test_enum_introspection(self):
        """Test enum types in introspection."""
        # Execute introspection query
        result = await self.handler.execute("""
            {
                __schema {
                    types {
                        kind
                        name
                        enumValues {
                            name
                        }
                    }
                }
            }
        """)

        # Find UserRole type
        types = result["data"]["__schema"]["types"]
        user_role_type = next((t for t in types if t["name"] == "UserRole"), None)

        assert user_role_type is not None
        assert user_role_type["kind"] == "ENUM"
        assert len(user_role_type["enumValues"]) == 3
        assert any(v["name"] == "ADMIN" for v in user_role_type["enumValues"])
        assert any(v["name"] == "USER" for v in user_role_type["enumValues"])
        assert any(v["name"] == "GUEST" for v in user_role_type["enumValues"])


class TestEnumQueryExecution:
    """Test enum query execution."""

    def setup_method(self):
        """Set up test environment."""
        self.er_diagram = BaseEntity.get_diagram()
        config_global_resolver(self.er_diagram)
        self.handler = GraphQLHandler(self.er_diagram)

    @pytest.mark.asyncio
    async def test_enum_field_query(self):
        """Test querying enum fields."""
        result = await self.handler.execute("{ usersWithRole { id name role } }")

        # Enum values should be serialized as their names (GraphQL convention)
        assert result["data"]["usersWithRole"][0]["role"] == "ADMIN"
        assert result["data"]["usersWithRole"][1]["role"] == "USER"

    @pytest.mark.asyncio
    async def test_post_status_enum_query(self):
        """Test querying post status enum fields."""
        result = await self.handler.execute("{ postsWithStatus { id title status } }")

        # Enum values should be serialized as their names (GraphQL convention)
        assert result["data"]["postsWithStatus"][0]["status"] == "PUBLISHED"
        assert result["data"]["postsWithStatus"][1]["status"] == "DRAFT"


class TestIntEnumQuery:
    """Test int enum query execution."""

    def setup_method(self):
        """Set up test environment."""
        self.er_diagram = BaseEntity.get_diagram()
        config_global_resolver(self.er_diagram)
        self.handler = GraphQLHandler(self.er_diagram)

    @pytest.mark.asyncio
    async def test_int_enum_field_query(self):
        """Test querying int enum fields."""
        result = await self.handler.execute("{ tasksWithPriority { id name priority } }")

        # IntEnum values should be serialized as their names (GraphQL convention)
        assert result["data"]["tasksWithPriority"][0]["priority"] == "HIGH"
        assert result["data"]["tasksWithPriority"][1]["priority"] == "LOW"
