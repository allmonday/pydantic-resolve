"""Tests for GraphQL exception helpers."""

from pydantic_resolve.graphql.exceptions import FieldNameConflictError


def test_field_name_conflict_error_custom_extensions():
    """FieldNameConflictError should expose custom extension payload."""
    err = FieldNameConflictError(
        message="conflict",
        entity_name="UserEntity",
        field_name="posts",
        conflict_type="SCALAR_CONFLICT",
        details={"extra": "value"},
    )

    payload = err.to_dict()

    assert payload["message"] == "conflict"
    assert payload["extensions"]["code"] == "FIELD_NAME_CONFLICT"
    assert payload["extensions"]["entity"] == "UserEntity"
    assert payload["extensions"]["field"] == "posts"
    assert payload["extensions"]["conflict_type"] == "SCALAR_CONFLICT"
    assert payload["extensions"]["extra"] == "value"
