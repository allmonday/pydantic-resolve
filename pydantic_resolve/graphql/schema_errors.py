"""Schema-construction errors for the entity GraphQL path.

These mirror the shape of the compose (UseCaseService) path's errors but live
in a separate module so the two intentionally-orthogonal code paths do not
couple at the type level. All checks fire eagerly at scan time — inside
``GraphQLHandler.__init__`` when the grouped query/mutation maps are built —
before any SDL/introspection is produced, so a broken entity graph never
silently drops methods.

Under the grouped layout the entity class name becomes both the root
Query/Mutation field name and the ``{Entity}Query`` / ``{Entity}Mutation`` type
name, and the method name is used verbatim as the field on that group type.
That makes name collisions destructive (silently clobbering a group or a
method), so they are rejected up front instead of last-writer-wins.
"""

from __future__ import annotations


# GraphQL root operation type names — an entity class named one of these would
# collide with the synthesized root types.
_RESERVED_ROOT_NAMES = frozenset({"Query", "Mutation", "Subscription"})


class EntitySchemaError(Exception):
    """Base class for entity-path schema construction errors."""


class DuplicateEntityError(EntitySchemaError):
    """Two distinct entity classes share the same ``__name__``.

    Under the grouped layout the entity class name becomes both the root
    Query/Mutation field name and the ``{Entity}Query`` group type name, so two
    same-named classes would collapse into one group and silently drop one
    entity's methods.
    """


class DuplicateMethodError(EntitySchemaError):
    """Two methods on the same entity produce the same GraphQL field name."""


class ReservedMethodFieldError(EntitySchemaError):
    """A ``@query``/``@mutation`` method name starts with ``__``.

    The ``__`` prefix is reserved by GraphQL introspection (``__schema``,
    ``__type``, ``__typename``) and cannot be used as a field name.
    """


class ReservedEntityError(EntitySchemaError):
    """An entity class is named ``Query`` / ``Mutation`` / ``Subscription``.

    Those names collide with the GraphQL root operation types and would
    produce self-referential, introspection-breaking schemas.
    """
