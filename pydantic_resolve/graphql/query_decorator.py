"""
Query decorator for marking Entity methods as GraphQL root queries.
"""

from typing import Callable, Optional, Union, overload


# Multiple overloads to support different calling patterns
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
