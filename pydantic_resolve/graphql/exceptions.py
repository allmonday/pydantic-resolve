"""
GraphQL-specific exceptions.
"""

from typing import Any, Dict, Optional


class GraphQLError(Exception):
    """Base exception for GraphQL errors."""

    def __init__(
        self,
        message: str,
        path: Optional[list] = None,
        extensions: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.path = path
        self.extensions = extensions or {}
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to GraphQL error format."""
        error_dict = {"message": self.message}
        if self.path:
            error_dict["path"] = self.path
        if self.extensions:
            error_dict["extensions"] = self.extensions
        return error_dict


class QueryParseError(GraphQLError):
    """Raised when GraphQL query parsing fails."""

    def __init__(self, message: str):
        super().__init__(
            message,
            extensions={"code": "GRAPHQL_PARSE_ERROR"}
        )


class ValidationError(GraphQLError):
    """Raised when GraphQL query validation fails."""

    def __init__(self, message: str, path: Optional[list] = None):
        super().__init__(
            message,
            path=path,
            extensions={"code": "GRAPHQL_VALIDATION_ERROR"}
        )


class ExecutionError(GraphQLError):
    """Raised when GraphQL query execution fails."""

    def __init__(self, message: str, path: Optional[list] = None):
        super().__init__(
            message,
            path=path,
            extensions={"code": "GRAPHQL_EXECUTION_ERROR"}
        )


class FieldNameConflictError(ValidationError):
    """Raised when field_name conflicts with other fields."""

    def __init__(
        self,
        message: str,
        entity_name: str,
        field_name: str,
        conflict_type: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize field name conflict error.

        Args:
            message: Error message
            entity_name: Name of the entity with the conflict
            field_name: Name of the conflicting field
            conflict_type: Type of conflict (SCALAR_CONFLICT, RELATIONSHIP_CONFLICT, INHERITANCE_CONFLICT)
            details: Additional conflict details
        """
        extensions = {
            "code": "FIELD_NAME_CONFLICT",
            "entity": entity_name,
            "field": field_name,
            "conflict_type": conflict_type
        }
        if details:
            extensions.update(details)

        super().__init__(message, extensions=extensions)

        self.entity_name = entity_name
        self.field_name = field_name
        self.conflict_type = conflict_type
        self.details = details or {}
