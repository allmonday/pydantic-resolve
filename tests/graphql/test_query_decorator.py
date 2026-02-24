"""
测试 @query 装饰器
"""

from pydantic_resolve import query


def test_query_decorator_sets_attributes():
    """测试 @query 装饰器正确设置函数属性"""

    @query(name='test_query', description='测试查询')
    async def my_query(cls, limit: int = 10):
        return []

    # 验证返回的是 classmethod
    assert isinstance(my_query, classmethod)

    # 验证属性被正确设置（在 __func__ 上）
    assert hasattr(my_query.__func__, '_pydantic_resolve_query')
    assert my_query.__func__._pydantic_resolve_query
    assert my_query.__func__._pydantic_resolve_query_name == 'test_query'
    assert my_query.__func__._pydantic_resolve_query_description == '测试查询'


def test_query_decorator_without_args():
    """测试不带参数的 @query 装饰器"""

    @query
    async def my_query(cls):
        return []

    # 验证返回的是 classmethod
    assert isinstance(my_query, classmethod)

    # 验证属性被正确设置（在 __func__ 上）
    assert hasattr(my_query.__func__, '_pydantic_resolve_query')
    assert my_query.__func__._pydantic_resolve_query
    assert my_query.__func__._pydantic_resolve_query_name is None
    assert my_query.__func__._pydantic_resolve_query_description is None
