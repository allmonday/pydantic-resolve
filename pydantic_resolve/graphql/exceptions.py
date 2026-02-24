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
