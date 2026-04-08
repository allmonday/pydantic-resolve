"""
GraphQL support for pydantic-resolve.

This module provides GraphQL query functionality that leverages the existing ERD
system to auto-generate schema and dynamically create Pydantic models based on
GraphQL queries.
"""

import warnings

# Core imports (require graphql-core)
try:
    from .decorator import query, mutation
    from .query_parser import QueryParser
    from .schema_builder import SchemaBuilder
    from .response_builder import ResponseBuilder
    from .types import FieldSelection, ParsedQuery
    from .exceptions import QueryParseError, GraphQLError
    from .handler import GraphQLHandler
    from .graphiql import get_graphiql_html

    CORE_AVAILABLE = True
except ImportError as e:
    CORE_AVAILABLE = False
    _core_import_error = str(e)
    warnings.warn(
        f"GraphQL core dependencies not available: {e}. "
        "Install with: pip install graphql-core"
    )

# Build exports list
if CORE_AVAILABLE:
    __all__ = [
        'query',
        'mutation',
        'GraphQLHandler',
        'QueryParser',
        'SchemaBuilder',
        'ResponseBuilder',
        'FieldSelection',
        'ParsedQuery',
        'QueryParseError',
        'GraphQLError',
        'get_graphiql_html',
    ]
else:
    __all__ = []
