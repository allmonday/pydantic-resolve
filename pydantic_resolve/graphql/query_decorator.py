"""
Query decorator for marking Entity methods as GraphQL root queries.
"""

from typing import Callable, Optional, Union, overload


# 多个重载以支持不同的调用方式
@overload
def query(func: Callable) -> classmethod: ...

@overload
def query(*, name: Optional[str] = None, description: Optional[str] = None) -> Callable: ...

def query(name_or_func: Union[str, Callable, None] = None, *, description: Optional[str] = None, name: Optional[str] = None):
    """
    将 Entity 的方法标记为 GraphQL 根查询。

    这个装饰器会自动实现 classmethod 的功能，因此不需要额外添加 @staticmethod 或 @classmethod。

    Args:
        func: 函数对象（当不带参数调用时）
        name: GraphQL 查询名称（默认将方法名转换为 camelCase）
        description: GraphQL Schema 中的描述文字

    使用示例:
        ```python
        from pydantic_resolve import base_entity, query

        BaseEntity = base_entity()

        class UserEntity(BaseModel, BaseEntity):
            id: int
            name: str

            @query(name='users', description='获取所有用户')
            async def get_all(cls, limit: int = 10):
                return await fetch_users(limit)

            @query  # 不带参数
            async def find_by_email(cls, email: str):
                return await fetch_user(email)
        ```

    这将生成以下 GraphQL Schema:
        ```graphql
        type Query {
            users(limit: Int): [User!]!
            findByEmail(email: String!): User
        }
        ```

    注意：
    - 方法签名中应该包含 `cls` 参数（即使不使用）
    - 方法会自动转换为 classmethod，可以直接通过类调用
    - 不需要额外添加 @staticmethod 或 @classmethod 装饰器
    """
    # 处理不带位置参数的装饰器：@query 或 @query(name='...')
    # 如果第一个参数是可调用的，说明是不带参数的装饰器: @query
    if callable(name_or_func):
        func = name_or_func
        # 在函数上设置元数据
        func._pydantic_resolve_query = True
        func._pydantic_resolve_query_name = name
        func._pydantic_resolve_query_description = description
        # 返回 classmethod
        return classmethod(func)

    # 处理带关键字参数的装饰器: @query(name='...', description='...')
    # name_or_func 是 None 或字符串（已废弃的用法）
    query_name = name or name_or_func

    def decorator(func: Callable) -> classmethod:
        # 在函数上设置元数据
        func._pydantic_resolve_query = True
        func._pydantic_resolve_query_name = query_name
        func._pydantic_resolve_query_description = description
        # 返回 classmethod
        return classmethod(func)

    return decorator
