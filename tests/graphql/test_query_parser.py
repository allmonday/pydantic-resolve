"""
测试 GraphQL 查询解析器
"""

import pytest
from pydantic_resolve.graphql import QueryParser, QueryParseError
from tests.graphql.fixtures.entities import BaseEntity


class TestQueryParser:
    """测试 QueryParser"""

    def setup_method(self):
        """设置测试环境"""
        self.er_diagram = BaseEntity.get_diagram()
        self.parser = QueryParser(self.er_diagram)

    def test_parse_simple_query(self):
        """测试解析简单查询"""
        query = "{ users { id name } }"
        parsed = self.parser.parse(query)

        assert parsed.root_entity.__name__ == 'UserEntity'
        assert 'users' in parsed.field_tree
        assert 'id' in parsed.field_tree['users'].sub_fields
        assert 'name' in parsed.field_tree['users'].sub_fields

    def test_parse_query_with_arguments(self):
        """测试解析带参数的查询"""
        query = "{ users(limit: 10) { id } }"
        parsed = self.parser.parse(query)

        assert parsed.root_entity.__name__ == 'UserEntity'
        assert 'users' in parsed.field_tree
        # 参数值会被正确转换为整数
        assert 'limit' in parsed.field_tree['users'].arguments
        assert parsed.field_tree['users'].arguments['limit'] == 10

    def test_parse_nested_query(self):
        """测试解析嵌套查询"""
        query = "{ users { id posts { title } } }"
        parsed = self.parser.parse(query)

        assert 'posts' in parsed.field_tree['users'].sub_fields
        assert 'title' in parsed.field_tree['users'].sub_fields['posts'].sub_fields

    def test_parse_invalid_query(self):
        """测试解析无效查询"""
        query = "{ invalid { id } }"

        # 解析器现在只检查语法，不验证实体是否存在
        # 未知查询的验证由处理器负责
        parsed = self.parser.parse(query)

        # 验证解析成功（语法正确）
        assert parsed is not None
        assert 'invalid' in parsed.field_tree
        # root_entity 可能为 None（如果无法推断）
        assert parsed.root_entity is None or parsed.root_entity.__name__ == 'InvalidEntity'

    def test_parse_empty_query(self):
        """测试解析空查询"""
        query = "{ }"

        with pytest.raises(QueryParseError):
            self.parser.parse(query)
