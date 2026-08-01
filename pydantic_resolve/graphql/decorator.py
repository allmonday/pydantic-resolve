"""
Decorators for marking Entity methods as GraphQL root queries and mutations.

Operations are grouped by entity: each entity's ``@query``/``@mutation`` methods
become the fields of a ``{Entity}Query`` / ``{Entity}Mutation`` group type, and the
root ``Query`` / ``Mutation`` mounts one field per entity. Method field names are
used verbatim (no entity prefix, no camelCase):

    UserEntity.get_all  ->  type Query { UserEntity: UserEntityQuery! }
                            type UserEntityQuery { get_all(...): [UserEntity!]! }

so a method is queried as ``{ UserEntity { get_all {} } }``.

Description is automatically extracted from the method's docstring.
"""

from typing import Callable
import pydantic_resolve.constant as const


# ============================================================================
# Query Decorator
# ============================================================================

def query(func: Callable) -> classmethod:
    """
    Mark Entity methods as GraphQL root queries.

    This decorator automatically implements classmethod functionality,
    so you don't need to add @staticmethod or @classmethod.

    Operations are grouped by entity; the method becomes a field on the
    ``{Entity}Query`` group type, named verbatim (e.g. ``UserEntity.get_all``
    -> field ``get_all`` on ``UserEntityQuery``).

    Description is automatically extracted from the method's docstring.

    Usage Examples:
        ```python
        from pydantic_resolve import base_entity, query

        BaseEntity = base_entity()

        class UserEntity(BaseModel, BaseEntity):
            id: int
            name: str

            @query
            async def get_all(cls, limit: int = 10):
                '''Get all users with pagination'''
                return await fetch_users(limit)
        ```

    This generates the following GraphQL Schema:
        ```graphql
        type Query {
            UserEntity: UserEntityQuery!
        }

        type UserEntityQuery {
            "Get all users with pagination"
            get_all(limit: Int): [UserEntity!]!
        }
        ```

    Notes:
        - Method signature should include `cls` parameter (even if unused)
        - Method is automatically converted to classmethod
        - No need to add @staticmethod or @classmethod decorator
        - The field name is the verbatim method name, mounted on the {Entity}Query group
        - Description is extracted from method's docstring
    """
    # Extract description from docstring
    description = func.__doc__.strip() if func.__doc__ else ""

    setattr(func, const.GRAPHQL_QUERY_ATTR, True)
    setattr(func, const.GRAPHQL_QUERY_DESCRIPTION_ATTR, description)
    return classmethod(func)


# ============================================================================
# Mutation Decorator
# ============================================================================

def mutation(func: Callable) -> classmethod:
    """
    Mark Entity methods as GraphQL root mutations.

    This decorator automatically implements classmethod functionality,
    so you don't need to add @staticmethod or @classmethod.

    Operations are grouped by entity; the method becomes a field on the
    ``{Entity}Mutation`` group type, named verbatim (e.g. ``UserEntity.create_user``
    -> field ``create_user`` on ``UserEntityMutation``).

    Description is automatically extracted from the method's docstring.

    Usage Examples:
        ```python
        from pydantic_resolve import base_entity, mutation

        BaseEntity = base_entity()

        class UserEntity(BaseModel, BaseEntity):
            id: int
            name: str
            email: str

            @mutation
            async def create_user(cls, name: str, email: str) -> 'UserEntity':
                '''Create a new user'''
                return await create_user_in_db(name, email)
        ```

    This generates the following GraphQL Schema:
        ```graphql
        type Mutation {
            UserEntity: UserEntityMutation!
        }

        type UserEntityMutation {
            "Create a new user"
            create_user(name: String!, email: String!): UserEntity!
        }
        ```

    Notes:
        - Method signature should include `cls` parameter (even if unused)
        - Method is automatically converted to classmethod
        - No need to add @staticmethod or @classmethod decorator
        - Return types follow GraphQL nullability rules:
            - `T` -> `T!` (non-null)
            - `Optional[T]` -> `T` (nullable)
            - `list[T]` -> `[T!]!` (non-null list of non-null items)
        - The field name is the verbatim method name, mounted on the {Entity}Mutation group
        - Description is extracted from method's docstring
    """
    # Extract description from docstring
    description = func.__doc__.strip() if func.__doc__ else ""

    setattr(func, const.GRAPHQL_MUTATION_ATTR, True)
    setattr(func, const.GRAPHQL_MUTATION_DESCRIPTION_ATTR, description)
    return classmethod(func)
