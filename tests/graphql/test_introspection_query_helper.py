"""Tests for IntrospectionQueryHelper - queries GraphQL introspection data.

Tests are designed based on interface contracts, focusing on input/output behavior.
"""

import pytest

from pydantic_resolve.graphql.mcp.builders.introspection_query_helper import IntrospectionQueryHelper


# === Fixtures ===

@pytest.fixture
def simple_introspection_data():
    """Minimal introspection data with User -> Post dependency."""
    return {
        "types": [
            # Query type
            {
                "name": "Query",
                "kind": "OBJECT",
                "fields": [
                    {
                        "name": "userGetAll",
                        "description": "Get all users",
                        "args": [],
                        "type": {"kind": "LIST", "name": None, "ofType": {"kind": "OBJECT", "name": "User", "ofType": None}},
                        "isDeprecated": False,
                        "deprecationReason": None,
                    },
                    {
                        "name": "userGetById",
                        "description": "Get user by ID",
                        "args": [],
                        "type": {"kind": "OBJECT", "name": "User", "ofType": None},
                        "isDeprecated": False,
                        "deprecationReason": None,
                    },
                ],
            },
            # Mutation type
            {
                "name": "Mutation",
                "kind": "OBJECT",
                "fields": [
                    {
                        "name": "createUser",
                        "description": "Create a new user",
                        "args": [],
                        "type": {"kind": "OBJECT", "name": "User", "ofType": None},
                        "isDeprecated": False,
                        "deprecationReason": None,
                    },
                ],
            },
            # User entity - references Post
            {
                "name": "User",
                "kind": "OBJECT",
                "fields": [
                    {"name": "id", "description": "User ID", "args": [], "type": {"kind": "SCALAR", "name": "Int", "ofType": None}, "isDeprecated": False, "deprecationReason": None},
                    {"name": "name", "description": "User name", "args": [], "type": {"kind": "SCALAR", "name": "String", "ofType": None}, "isDeprecated": False, "deprecationReason": None},
                    {
                        "name": "posts",
                        "description": "User's posts",
                        "args": [],
                        "type": {"kind": "LIST", "name": None, "ofType": {"kind": "OBJECT", "name": "Post", "ofType": None}},
                        "isDeprecated": False,
                        "deprecationReason": None,
                    },
                ],
            },
            # Post entity - references User (circular)
            {
                "name": "Post",
                "kind": "OBJECT",
                "fields": [
                    {"name": "id", "description": "Post ID", "args": [], "type": {"kind": "SCALAR", "name": "Int", "ofType": None}, "isDeprecated": False, "deprecationReason": None},
                    {"name": "title", "description": "Post title", "args": [], "type": {"kind": "SCALAR", "name": "String", "ofType": None}, "isDeprecated": False, "deprecationReason": None},
                    {
                        "name": "author",
                        "description": "Post author",
                        "args": [],
                        "type": {"kind": "OBJECT", "name": "User", "ofType": None},
                        "isDeprecated": False,
                        "deprecationReason": None,
                    },
                ],
            },
            # Scalar types
            {"name": "String", "kind": "SCALAR", "fields": None, "inputFields": None, "interfaces": None, "enumValues": None, "possibleTypes": None},
            {"name": "Int", "kind": "SCALAR", "fields": None, "inputFields": None, "interfaces": None, "enumValues": None, "possibleTypes": None},
        ]
    }


@pytest.fixture
def entity_names():
    """Entity names that should be traced."""
    return {"User", "Post"}


@pytest.fixture
def helper(simple_introspection_data, entity_names):
    """IntrospectionQueryHelper instance with simple data."""
    return IntrospectionQueryHelper(simple_introspection_data, entity_names)


# === Test __init__ ===

class TestInit:
    """Tests for IntrospectionQueryHelper initialization."""

    def test_normal_initialization(self, simple_introspection_data, entity_names):
        """Should build type cache from introspection data."""
        helper = IntrospectionQueryHelper(simple_introspection_data, entity_names)
        # Verify internal state by using public methods
        assert helper.get_operation_field("Query", "userGetAll") is not None
        assert helper.get_operation_field("Query", "nonexistent") is None

    def test_empty_types_list(self, entity_names):
        """Should handle empty types list."""
        data = {"types": []}
        helper = IntrospectionQueryHelper(data, entity_names)
        assert helper.list_operation_fields("Query") == []

    def test_empty_entity_names(self, simple_introspection_data):
        """Should work with empty entity names (no types will be traced)."""
        helper = IntrospectionQueryHelper(simple_introspection_data, set())
        type_ref = {"kind": "OBJECT", "name": "User", "ofType": None}
        result = helper.collect_related_types(type_ref)
        assert result == set()


# === Test collect_related_types ===

class TestCollectRelatedTypes:
    """Tests for collect_related_types method."""

    def test_none_input(self, helper):
        """None input should return empty set."""
        result = helper.collect_related_types(None)
        assert result == set()

    def test_scalar_type(self, helper):
        """SCALAR type should return empty set (scalars are not entities)."""
        type_ref = {"kind": "SCALAR", "name": "String", "ofType": None}
        result = helper.collect_related_types(type_ref)
        assert result == set()

    def test_object_type_in_entity_names(self, helper):
        """OBJECT type in entity_names should return set containing that type and its dependencies."""
        type_ref = {"kind": "OBJECT", "name": "User", "ofType": None}
        result = helper.collect_related_types(type_ref)
        # User has posts field referencing Post, so both are returned
        assert result == {"User", "Post"}

    def test_object_type_not_in_entity_names(self, helper):
        """OBJECT type not in entity_names should return empty set."""
        type_ref = {"kind": "OBJECT", "name": "SomeOtherType", "ofType": None}
        result = helper.collect_related_types(type_ref)
        assert result == set()

    def test_list_wrapper(self, helper):
        """LIST wrapper should unwrap and continue tracing."""
        type_ref = {"kind": "LIST", "name": None, "ofType": {"kind": "OBJECT", "name": "User", "ofType": None}}
        result = helper.collect_related_types(type_ref)
        # User has posts field referencing Post
        assert result == {"User", "Post"}

    def test_non_null_wrapper(self, helper):
        """NON_NULL wrapper should unwrap and continue tracing."""
        type_ref = {"kind": "NON_NULL", "name": None, "ofType": {"kind": "OBJECT", "name": "User", "ofType": None}}
        result = helper.collect_related_types(type_ref)
        # User has posts field referencing Post
        assert result == {"User", "Post"}

    def test_nested_wrappers(self, helper):
        """Nested LIST/NON_NULL wrappers should be correctly resolved."""
        # [User!]! -> NON_NULL(LIST(NON_NULL(User)))
        type_ref = {
            "kind": "NON_NULL",
            "name": None,
            "ofType": {
                "kind": "LIST",
                "name": None,
                "ofType": {"kind": "OBJECT", "name": "User", "ofType": None},
            },
        }
        result = helper.collect_related_types(type_ref)
        # User has posts field referencing Post
        assert result == {"User", "Post"}

    def test_recursive_field_dependencies(self, helper):
        """Type with fields referencing other entities should collect all dependencies."""
        # User has posts field referencing Post
        type_ref = {"kind": "OBJECT", "name": "User", "ofType": None}
        result = helper.collect_related_types(type_ref)
        # User references Post via posts field
        assert "User" in result
        assert "Post" in result

    def test_circular_dependency(self, helper):
        """Circular dependency (A -> B -> A) should not cause infinite loop."""
        # User -> Post -> User (circular)
        type_ref = {"kind": "OBJECT", "name": "User", "ofType": None}
        # Should complete without hanging
        result = helper.collect_related_types(type_ref)
        # Each type should appear only once
        assert result == {"User", "Post"}

    def test_input_object_collects_nested_enum_types(self, entity_names):
        """INPUT_OBJECT should include itself and nested enum/input dependencies."""
        data = {
            "types": [
                {
                    "name": "CreateUserInput",
                    "kind": "INPUT_OBJECT",
                    "inputFields": [
                        {"name": "name", "type": {"kind": "SCALAR", "name": "String", "ofType": None}},
                        {"name": "role", "type": {"kind": "ENUM", "name": "UserRole", "ofType": None}},
                    ],
                    "fields": None,
                },
                {
                    "name": "UserRole",
                    "kind": "ENUM",
                    "enumValues": [
                        {"name": "ADMIN"},
                        {"name": "USER"},
                    ],
                    "fields": None,
                    "inputFields": None,
                },
                {"name": "String", "kind": "SCALAR", "fields": None, "inputFields": None},
            ]
        }
        helper = IntrospectionQueryHelper(data, entity_names)

        result = helper.collect_related_types(
            {"kind": "INPUT_OBJECT", "name": "CreateUserInput", "ofType": None}
        )

        assert result == {"CreateUserInput", "UserRole"}


# === Test get_introspection_for_types ===

class TestGetIntrospectionForTypes:
    """Tests for get_introspection_for_types method."""

    def test_empty_set(self, helper):
        """Empty set should return empty list."""
        result = helper.get_introspection_for_types(set())
        assert result == []

    def test_single_type(self, helper):
        """Single existing type should return list with one element."""
        result = helper.get_introspection_for_types({"User"})
        assert len(result) == 1
        assert result[0]["name"] == "User"
        assert result[0]["kind"] == "OBJECT"

    def test_multiple_types_sorted(self, helper):
        """Multiple types should be returned sorted by name."""
        result = helper.get_introspection_for_types({"Post", "User"})
        assert len(result) == 2
        # Sorted alphabetically
        assert result[0]["name"] == "Post"
        assert result[1]["name"] == "User"

    def test_non_existent_types(self, helper):
        """Non-existent type names should be skipped."""
        result = helper.get_introspection_for_types({"NonExistent"})
        assert result == []

    def test_mixed_existing_and_non_existing(self, helper):
        """Mix of existing and non-existing should only return existing."""
        result = helper.get_introspection_for_types({"User", "NonExistent", "Post"})
        assert len(result) == 2
        names = [t["name"] for t in result]
        assert "User" in names
        assert "Post" in names
        assert "NonExistent" not in names


# === Test get_operation_field ===

class TestGetOperationField:
    """Tests for get_operation_field method."""

    def test_existing_field(self, helper):
        """Existing field should return field info."""
        result = helper.get_operation_field("Query", "userGetAll")
        assert result is not None
        assert result["name"] == "userGetAll"
        assert result["description"] == "Get all users"

    def test_non_existent_field_name(self, helper):
        """Non-existent field name should return None."""
        result = helper.get_operation_field("Query", "nonexistent")
        assert result is None

    def test_non_existent_operation_type(self, helper):
        """Non-existent operation type should return None."""
        result = helper.get_operation_field("Subscription", "onUserCreated")
        assert result is None

    def test_operation_type_with_no_fields(self, entity_names):
        """Operation type with no fields should return None for any field."""
        data = {
            "types": [
                {"name": "Query", "kind": "OBJECT", "fields": None},
            ]
        }
        helper = IntrospectionQueryHelper(data, entity_names)
        result = helper.get_operation_field("Query", "anyField")
        assert result is None


# === Test list_operation_fields ===

class TestListOperationFields:
    """Tests for list_operation_fields method."""

    def test_list_query_fields(self, helper):
        """Should list all Query fields."""
        result = helper.list_operation_fields("Query")
        assert len(result) == 2
        names = [f["name"] for f in result]
        assert "userGetAll" in names
        assert "userGetById" in names

    def test_list_mutation_fields(self, helper):
        """Should list all Mutation fields."""
        result = helper.list_operation_fields("Mutation")
        assert len(result) == 1
        assert result[0]["name"] == "createUser"

    def test_non_existent_operation_type(self, helper):
        """Non-existent operation type should return empty list."""
        result = helper.list_operation_fields("Subscription")
        assert result == []

    def test_returns_only_name_and_description(self, helper):
        """Return structure should only contain name and description."""
        result = helper.list_operation_fields("Query")
        for field in result:
            assert set(field.keys()) == {"name", "description"}
            assert isinstance(field["name"], str)
            assert field["description"] is None or isinstance(field["description"], str)


# === Test get_operation_with_related_types ===

class TestGetOperationWithRelatedTypes:
    """Tests for get_operation_with_related_types method."""

    def test_existing_operation(self, helper):
        """Existing operation should return complete structure."""
        result = helper.get_operation_with_related_types("Query", "userGetAll")
        assert result is not None
        assert "operation" in result
        assert "related_types" in result
        assert result["operation"]["name"] == "userGetAll"

    def test_non_existent_operation(self, helper):
        """Non-existent operation should return None."""
        result = helper.get_operation_with_related_types("Query", "nonexistent")
        assert result is None

    def test_related_types_collected(self, helper):
        """Related types should be correctly collected."""
        # userGetAll returns [User], User has posts field referencing Post
        result = helper.get_operation_with_related_types("Query", "userGetAll")
        assert result is not None
        type_names = [t["name"] for t in result["related_types"]]
        assert "User" in type_names
        assert "Post" in type_names

    def test_operation_with_no_entity_dependencies(self, entity_names):
        """Operation returning scalar should have empty related_types."""
        data = {
            "types": [
                {
                    "name": "Query",
                    "kind": "OBJECT",
                    "fields": [
                        {
                            "name": "ping",
                            "description": "Health check",
                            "args": [],
                            "type": {"kind": "SCALAR", "name": "String", "ofType": None},
                            "isDeprecated": False,
                            "deprecationReason": None,
                        },
                    ],
                },
                {"name": "String", "kind": "SCALAR", "fields": None, "inputFields": None, "interfaces": None, "enumValues": None, "possibleTypes": None},
            ]
        }
        helper = IntrospectionQueryHelper(data, entity_names)
        result = helper.get_operation_with_related_types("Query", "ping")
        assert result is not None
        assert result["related_types"] == []
