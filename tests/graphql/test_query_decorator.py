"""
测试 @query 装饰器
"""

from pydantic_resolve import query
import pydantic_resolve.constant as const


def test_query_decorator_sets_attributes():
    """测试 @query 装饰器正确设置函数属性"""

    @query
    async def my_query(cls, limit: int = 10):
        """测试查询"""
        return []

    # 验证返回的是 classmethod
    assert isinstance(my_query, classmethod)

    # 验证属性被正确设置（在 __func__ 上）
    assert hasattr(my_query.__func__, const.GRAPHQL_QUERY_ATTR)
    assert getattr(my_query.__func__, const.GRAPHQL_QUERY_ATTR)
    assert getattr(my_query.__func__, const.GRAPHQL_QUERY_DESCRIPTION_ATTR) == "测试查询"


def test_query_decorator_without_docstring():
    """测试不带 docstring 的 @query 装饰器"""

    @query
    async def my_query(cls):
        return []

    # 验证返回的是 classmethod
    assert isinstance(my_query, classmethod)

    # 验证属性被正确设置（在 __func__ 上）
    assert hasattr(my_query.__func__, const.GRAPHQL_QUERY_ATTR)
    assert getattr(my_query.__func__, const.GRAPHQL_QUERY_ATTR)
    assert getattr(my_query.__func__, const.GRAPHQL_QUERY_DESCRIPTION_ATTR) == ""
