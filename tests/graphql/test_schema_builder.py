"""
测试 GraphQL Schema 生成器
"""

from pydantic_resolve.graphql import SchemaBuilder
from tests.graphql.fixtures.entities import BaseEntity


class TestSchemaBuilder:
    """测试 SchemaBuilder"""

    def setup_method(self):
        """设置测试环境"""
        self.er_diagram = BaseEntity.get_diagram()
        self.builder = SchemaBuilder(self.er_diagram)

    def test_build_schema(self):
        """测试生成完整 Schema"""
        schema = self.builder.build_schema()

        # 验证 Schema 包含类型定义
        assert 'type UserEntity' in schema
        assert 'type PostEntity' in schema

        # 验证 Schema 包含 Query 定义
        assert 'type Query' in schema

        # 验证 Schema 包含查询方法
        assert 'users' in schema or 'all' in schema
        assert 'posts' in schema or 'all' in schema

    def test_extract_query_methods(self):
        """测试提取 @query 方法"""
        # 获取 UserEntity
        user_entity_cfg = None
        for cfg in self.er_diagram.configs:
            if cfg.kls.__name__ == 'UserEntity':
                user_entity_cfg = cfg
                break

        assert user_entity_cfg is not None

        methods = self.builder._extract_query_methods(user_entity_cfg.kls)

        # 验证提取到的方法
        assert len(methods) > 0

        # 验证方法属性
        method_names = [m['name'] for m in methods]
        assert 'all' in method_names or 'get_all' in method_names
        assert 'user' in method_names or 'get_by_id' in method_names

    def test_map_python_type_to_gql(self):
        """测试 Python 类型到 GraphQL 类型的映射"""

        # 测试基础类型
        assert 'Int!' in self.builder._map_python_type_to_gql(int)
        assert 'String!' in self.builder._map_python_type_to_gql(str)
        assert 'Boolean!' in self.builder._map_python_type_to_gql(bool)

        # 测试 Optional 类型
        from typing import Optional
        gql_type = self.builder._map_python_type_to_gql(Optional[int])
        assert 'Int' in gql_type
