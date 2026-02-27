"""
Decorators for marking Entity methods as GraphQL root queries and mutations.
"""

from typing import Callable, Optional, Union, overload


# ============================================================================
# Query Decorator
# ============================================================================

@overload
def query(func: Callable) -> classmethod: ...


@overload
def query(*, name: Optional[str] = None, description: Optional[str] = None) -> Callable: ...


def query(name_or_func: Union[str, Callable, None] = None, *, description: Optional[str] = None, name: Optional[str] = None):
    """
    Mark Entity methods as GraphQL root queries.

    This decorator automatically implements classmethod functionality,
    so you don't need to add @staticmethod or @classmethod.

    Args:
        func: Function object (when called without parameters)
        name: GraphQL query name (defaults to camelCase conversion of method name)
        description: Description text in GraphQL Schema

    Usage Examples:
        ```python
        from pydantic_resolve import base_entity, query

        BaseEntity = base_entity()

        class UserEntity(BaseModel, BaseEntity):
            id: int
            name: str

            @query(name='users', description='Get all users')
            async def get_all(cls, limit: int = 10):
                return await fetch_users(limit)

            @query  # without parameters
            async def find_by_email(cls, email: str):
                return await fetch_user(email)
        ```

    This generates the following GraphQL Schema:
        ```graphql
        type Query {
            users(limit: Int): [User!]!
            findByEmail(email: String!): User
        }
        ```

    Notes:
        - Method signature should include `cls` parameter (even if unused)
        - Method is automatically converted to classmethod
        - No need to add @staticmethod or @classmethod decorator
    """
    # Handle decorator without positional arguments: @query or @query(name='...')
    # If first parameter is callable, it's the decorator without parameters: @query
    if callable(name_or_func):
        func = name_or_func
        # Set metadata on function
        func._pydantic_resolve_query = True
        func._pydantic_resolve_query_name = name
        func._pydantic_resolve_query_description = description
        # Return classmethod
        return classmethod(func)

    # Handle decorator with keyword arguments: @query(name='...', description='...')
    # name_or_func is None or string (deprecated usage)
    query_name = name or name_or_func

    def decorator(func: Callable) -> classmethod:
        # Set metadata on function
        func._pydantic_resolve_query = True
        func._pydantic_resolve_query_name = query_name
        func._pydantic_resolve_query_description = description
        # Return classmethod
        return classmethod(func)

    return decorator


# ============================================================================
# Mutation Decorator
# ============================================================================

@overload
def mutation(func: Callable) -> classmethod: ...


@overload
def mutation(*, name: Optional[str] = None, description: Optional[str] = None) -> Callable: ...


def mutation(name_or_func: Union[str, Callable, None] = None, *, description: Optional[str] = None, name: Optional[str] = None):
    """
    Mark Entity methods as GraphQL root mutations.

    This decorator automatically implements classmethod functionality,
    so you don't need to add @staticmethod or @classmethod.

    Args:
        func: Function object (when called without parameters)
        name: GraphQL mutation name (defaults to camelCase conversion of method name)
        description: Description text in GraphQL Schema

    Usage Examples:
        ```python
        from pydantic_resolve import base_entity, mutation

        BaseEntity = base_entity()

        class UserEntity(BaseModel, BaseEntity):
            id: int
            name: str
            email: str

            @mutation(name='createUser', description='Create a new user')
            async def create_user(cls, name: str, email: str) -> 'UserEntity':
                return await create_user_in_db(name, email)

            @mutation  # without parameters
            async def delete_user(cls, id: int) -> bool:
                return await delete_user_from_db(id)
        ```

    This generates the following GraphQL Schema:
        ```graphql
        type Mutation {
            createUser(name: String!, email: String!): User!
            deleteUser(id: Int!): Boolean!
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
    """
    # Handle decorator without parameters: @mutation
    # If first parameter is callable, it's the decorator without parameters: @mutation
    if callable(name_or_func):
        func = name_or_func
        # Set metadata on function
        func._pydantic_resolve_mutation = True
        func._pydantic_resolve_mutation_name = name
        func._pydantic_resolve_mutation_description = description
        # Return classmethod
        return classmethod(func)

    # Handle decorator with parameters: @mutation(name='...', description='...')
    # name_or_func is None or string (deprecated usage)
    mutation_name = name or name_or_func

    def decorator(func: Callable) -> classmethod:
        # Set metadata on function
        func._pydantic_resolve_mutation = True
        func._pydantic_resolve_mutation_name = mutation_name
        func._pydantic_resolve_mutation_description = description
        # Return classmethod
        return classmethod(func)

    return decorator
