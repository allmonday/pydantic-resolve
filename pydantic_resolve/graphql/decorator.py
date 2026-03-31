"""
Decorators for marking Entity methods as GraphQL root queries and mutations.

The GraphQL operation name is automatically generated from entity name + method name
using camelCase style: entityPrefix + MethodCamel
(e.g., UserEntity.get_all -> userEntityGetAll)

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

    The GraphQL query name is automatically generated as: entityPrefix + MethodCamel
    (e.g., User.get_all -> userGetAll, PostEntity.find_by_id -> postEntityFindById)

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
            "Get all users with pagination"
            userEntityGetAll(limit: Int): [UserEntity!]!
        }
        ```

    Notes:
        - Method signature should include `cls` parameter (even if unused)
        - Method is automatically converted to classmethod
        - No need to add @staticmethod or @classmethod decorator
        - Query name is auto-generated from EntityName + method_name
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

    The GraphQL mutation name is automatically generated as: entityPrefix + MethodCamel
    (e.g., User.create_user -> userCreateUser, PostEntity.delete -> postEntityDelete)

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
            "Create a new user"
            userEntityCreateUser(name: String!, email: String!): UserEntity!
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
        - Mutation name is auto-generated from EntityName + method_name
        - Description is extracted from method's docstring
    """
    # Extract description from docstring
    description = func.__doc__.strip() if func.__doc__ else ""

    setattr(func, const.GRAPHQL_MUTATION_ATTR, True)
    setattr(func, const.GRAPHQL_MUTATION_DESCRIPTION_ATTR, description)
    return classmethod(func)
