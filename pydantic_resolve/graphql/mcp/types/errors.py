"""Error handling utilities for MCP server."""

from enum import Enum
from typing import Any, Dict


class MCPErrors(str, Enum):
    """Error types for MCP operations."""

    APP_NOT_FOUND = "app_not_found"
    QUERY_EXECUTION_ERROR = "query_execution_error"
    MUTATION_EXECUTION_ERROR = "mutation_execution_error"
    TYPE_NOT_FOUND = "type_not_found"
    OPERATION_NOT_FOUND = "operation_not_found"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INTERNAL_ERROR = "internal_error"


def create_error_response(error: str, error_type: MCPErrors, hint: str | None = None) -> Dict[str, Any]:
    """Create a standardized error response.

    Args:
        error: Error message
        error_type: Error type enum value
        hint: Optional hint for the user

    Returns:
        Dictionary with error information
    """
    result = {
        "success": False,
        "error": error,
        "error_type": error_type.value,
    }
    if hint:
        result["hint"] = hint
    return result


def create_success_response(data: Any, hint: str | None = None) -> Dict[str, Any]:
    """Create a standardized success response.

    Args:
        data: Response data
        hint: Optional hint for the user

    Returns:
        Dictionary with success information
    """
    result = {
        "success": True,
        "data": data,
    }
    if hint:
        result["hint"] = hint
    return result
