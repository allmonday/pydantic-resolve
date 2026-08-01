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

        # 验证分组结构：根 Query 上每个 entity 一个挂载字段，
        # 方法字段落在 {Entity}Query 组类型里，方法名用原名。
        assert 'UserEntity: UserEntityQuery!' in schema
        assert 'PostEntity: PostEntityQuery!' in schema
        assert 'type UserEntityQuery' in schema
        assert 'get_all' in schema

    def test_extract_query_methods(self):
        """测试提取 @query 方法"""
        # 获取 UserEntity
        user_entity_cfg = None
        for cfg in self.er_diagram.entities:
            if cfg.kls.__name__ == 'UserEntity':
                user_entity_cfg = cfg
                break

        assert user_entity_cfg is not None

        methods = self.builder._extract_query_methods(user_entity_cfg.kls)

        # 验证提取到的方法
        assert len(methods) > 0

        # 验证方法属性 (分组布局下用原方法名)
        method_names = [m['name'] for m in methods]
        assert 'get_all' in method_names
        assert 'get_by_id' in method_names

    def test_forward_ref_type_in_schema(self):
        """测试 ForwardRef 类型在 Schema 中正确解析"""
        schema = self.builder.build_schema()

        # 验证 CommentEntity 类型被正确生成
        assert 'type CommentEntity' in schema

        # 验证 get_comments 查询返回正确的类型
        assert 'get_comments' in schema
        # 验证返回类型是 [CommentEntity] 而不是 [String] 或 [PostEntity]
        # 查找 get_comments 行并检查返回类型
        lines = schema.split('\n')
        matched_line = next((line for line in lines if 'get_comments' in line), None)
        assert matched_line is not None, "get_comments not found in schema"
        assert ': [CommentEntity]' in matched_line or ': [CommentEntity!]' in matched_line, \
            f"get_comments should return [CommentEntity], but schema shows: {matched_line}"
