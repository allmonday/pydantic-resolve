"""
GraphQL support for pydantic-resolve.

This module provides GraphQL query functionality that leverages the existing ERD
system to auto-generate schema and dynamically create Pydantic models based on
GraphQL queries.
"""

import warnings

# Core imports (require graphql-core)
try:
    from .query_decorator import query
    from .query_parser import QueryParser
    from .schema_builder import SchemaBuilder
    from .response_builder import ResponseBuilder
    from .types import FieldSelection, ParsedQuery
    from .exceptions import QueryParseError, GraphQLError
    from .handler import GraphQLHandler

    CORE_AVAILABLE = True
except ImportError as e:
    CORE_AVAILABLE = False
    _core_import_error = str(e)
    warnings.warn(
        f"GraphQL core dependencies not available: {e}. "
        "Install with: pip install graphql-core"
    )

# FastAPI integration (requires fastapi)
try:
    from .handler import create_graphql_route  # noqa: F401 - re-exported in __all__
    FASTAPI_INTEGRATION_AVAILABLE = True
except ImportError as e:
    FASTAPI_INTEGRATION_AVAILABLE = False
    _fastapi_import_error = str(e)
    # Don't warn here - FastAPI is optional

# Build exports list
if CORE_AVAILABLE:
    __all__ = [
        'query',
        'GraphQLHandler',
        'QueryParser',
        'SchemaBuilder',
        'ResponseBuilder',
        'FieldSelection',
        'ParsedQuery',
        'QueryParseError',
        'GraphQLError',
    ]

    if FASTAPI_INTEGRATION_AVAILABLE:
        __all__.append('create_graphql_route')
else:
    __all__ = []
