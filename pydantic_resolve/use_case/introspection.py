"""Introspection support for the UseCase compose surface.

Two siblings:

- :func:`is_introspection_query` — cheap keyword-based detector used by
  ``compose_query`` to reject (or by HTTP handlers to route) ``__schema``
  / ``__type`` / ``__typename`` queries.
- :func:`compose_introspect` — runs a GraphQL introspection query against
  the app's cached ``compose_schema``, returning the standard
  ``{data, errors}`` envelope.

These live separately from :mod:`compose` because the execution pipeline
in ``compose.py`` handles *data* queries only; introspection is a
parallel path that callers must dispatch to explicitly.
"""

from __future__ import annotations

from typing import Any

from graphql import graphql_sync

from pydantic_resolve.use_case.compose import ComposeError


_INTROSPEPTION_KEYWORDS: tuple[str, ...] = ("__schema", "__type", "__typename")


def is_introspection_query(query: str) -> bool:
    """Return True if ``query`` is a GraphQL introspection query.

    Detects ``__schema`` / ``__type`` / ``__typename`` anywhere in the
    query body. Mirrors the keyword-based detection used by the existing
    Entity GraphQLHandler (see ``pydantic_resolve/graphql/introspection.py``).
    """
    if not query:
        return False
    return any(kw in query for kw in _INTROSPEPTION_KEYWORDS)


def compose_introspect(
    app: Any,
    query: str | None = None,
) -> dict[str, Any]:
    """Run a GraphQL introspection query against the app's compose schema.

    Args:
        app: :class:`UseCaseResources` instance. Reads ``app.compose_schema``
            (built once at registration).
        query: GraphQL query string targeting ``__schema`` / ``__type`` /
            ``__typename``. If ``None``, runs the canonical full-schema
            introspection query (the one GraphiQL sends on startup).

    Returns:
        Standard GraphQL response envelope::

            {"data": {...}, "errors": None or [...]}

    Raises:
        ComposeError: If the schema is missing or the query fails to execute.
    """
    schema = getattr(app, "compose_schema", None)
    if schema is None:
        raise ComposeError(
            "App has no cached compose_schema; was it built via UseCaseManager?",
            "internal_error",
        )

    actual_query = query if query is not None else _FULL_INTROSPEPTION_QUERY
    result = graphql_sync(schema, actual_query)

    if result.errors:
        messages = [
            err.message if hasattr(err, "message") else str(err)
            for err in result.errors
        ]
        raise ComposeError(
            f"Introspection query failed: {'; '.join(messages)}",
            "validation_error",
        )

    return {"data": result.data, "errors": None}


# Canonical introspection query — subset of what GraphiQL sends.
# Includes __schema with all standard fields and __type(name:) lookup.
_FULL_INTROSPEPTION_QUERY = """
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    subscriptionType { name }
    types {
      ...FullType
    }
    directives {
      name
      description
      locations
      args {
        ...InputValue
      }
    }
  }
}

fragment FullType on __Type {
  kind
  name
  description
  fields(includeDeprecated: true) {
    name
    description
    args {
      ...InputValue
    }
    type {
      ...TypeRef
    }
    isDeprecated
    deprecationReason
  }
  inputFields {
    ...InputValue
  }
  interfaces {
    ...TypeRef
  }
  enumValues(includeDeprecated: true) {
    name
    description
    isDeprecated
    deprecationReason
  }
  possibleTypes {
    ...TypeRef
  }
}

fragment InputValue on __InputValue {
  name
  description
  type { ...TypeRef }
  defaultValue
}

fragment TypeRef on __Type {
  kind
  name
  ofType {
    kind
    name
    ofType {
      kind
      name
      ofType {
        kind
        name
        ofType {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
              }
            }
          }
        }
      }
    }
  }
}
"""

__all__ = ["is_introspection_query", "compose_introspect"]
