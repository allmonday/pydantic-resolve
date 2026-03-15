"""
Decorators for marking Entity methods as GraphQL root queries and mutations.

The GraphQL operation name is automatically generated from entity name + method name
using camelCase style: entityPrefix + MethodCamel
(e.g., UserEntity.get_all -> userEntityGetAll)
"""

from typing import Callable, Optional


# ============================================================================
# Query Decorator
# ============================================================================

def query(*, description: Optional[str] = None):
    """
    Mark Entity methods as GraphQL root queries.

    This decorator automatically implements classmethod functionality,
    so you don't need to add @staticmethod or @classmethod.

    The GraphQL query name is automatically generated as: entityPrefix + MethodCamel
    (e.g., User.get_all -> userGetAll, PostEntity.find_by_id -> postEntityFindById)

    Args:
        description: Optional description text in GraphQL Schema

    Usage Examples:
        ```python
        from pydantic_resolve import base_entity, query

        BaseEntity = base_entity()

        class UserEntity(BaseModel, BaseEntity):
            id: int
            name: str

            @query(description='Get all users')
            async def get_all(cls, limit: int = 10):
                return await fetch_users(limit)

            @query  # without parameters
            async def find_by_email(cls, email: str):
                return await fetch_user(email)
        ```

    This generates the following GraphQL Schema:
        ```graphql
        type Query {
            userEntityGetAll(limit: Int): [UserEntity!]!
            userEntityFindByEmail(email: String!): UserEntity
        }
        ```

    Notes:
        - Method signature should include `cls` parameter (even if unused)
        - Method is automatically converted to classmethod
        - No need to add @staticmethod or @classmethod decorator
        - Query name is auto-generated from EntityName + method_name
    """
    def decorator(func: Callable) -> classmethod:
        # Set metadata on function
        func._pydantic_resolve_query = True
        func._pydantic_resolve_query_description = description
        # Return classmethod
        return classmethod(func)

    return decorator


# ============================================================================
# Mutation Decorator
# ============================================================================

def mutation(*, description: Optional[str] = None):
    """
    Mark Entity methods as GraphQL root mutations.

    This decorator automatically implements classmethod functionality,
    so you don't need to add @staticmethod or @classmethod.

    The GraphQL mutation name is automatically generated as: entityPrefix + MethodCamel
    (e.g., User.create_user -> userCreateUser. PostEntity.delete -> postEntityDelete)

    Args:
        description: Optional description text in GraphQL Schema

    Usage Examples:
        ```python
        from pydantic_resolve import base_entity, mutation

        BaseEntity = base_entity()

        class UserEntity(BaseModel, BaseEntity):
            id: int
            name: str
            email: str

            @mutation(description='Create a new user')
            async def create_user(cls, name: str, email: str) -> 'UserEntity':
                return await create_user_in_db(name, email)

            @mutation  # without parameters
            async def delete_user(cls, id: int) -> bool:
                return await delete_user_from_db(id)
        ```

    This generates the following GraphQL Schema:
        ```graphql
        type Mutation {
            userEntityCreateUser(name: String!, email: String!): UserEntity!
            userEntityDeleteUser(id: Int!): Boolean!
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
    """
    def decorator(func: Callable) -> classmethod:
        # Set metadata on function
        func._pydantic_resolve_mutation = True
        func._pydantic_resolve_mutation_description = description
        # Return classmethod
        return classmethod(func)

    return decorator
