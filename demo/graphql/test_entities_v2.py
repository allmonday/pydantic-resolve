"""
测试 entities_v2.py - 验证 ErDiagram 方式与 @query/@mutation 装饰器结合使用

验证点：
1. @query 装饰器能被正确识别
2. @mutation 装饰器能被正确识别
3. GraphQLHandler 能正确执行查询和变更
4. 关系解析能正常工作
"""

import pytest
import asyncio
from demo.graphql.entities_v2 import (
    diagram_v2,
    UserEntityV2,
    PostEntityV2,
    CommentEntityV2,
    init_db_v2,
    users_db_v2,
    posts_db_v2,
    comments_db_v2,
)
from pydantic_resolve.graphql import GraphQLHandler
from pydantic_resolve import config_global_resolver


@pytest.fixture
def handler():
    """创建 GraphQLHandler 实例"""
    # 重新初始化数据库，确保测试状态干净
    init_db_v2()
    # 重新配置全局 resolver
    config_global_resolver(diagram_v2)
    return GraphQLHandler(diagram_v2, enable_from_attribute_in_type_adapter=True)


class TestQueryRecognition:
    """测试 @query 装饰器识别"""

    def test_handler_has_query_map(self, handler):
        """验证 handler 正确构建了 query_map"""
        assert hasattr(handler, 'query_map')
        assert len(handler.query_map) > 0

    def test_users_v2_query_exists(self, handler):
        """验证 users_v2 查询被识别"""
        assert 'users_v2' in handler.query_map

    def test_user_v2_query_exists(self, handler):
        """验证 user_v2 查询被识别"""
        assert 'user_v2' in handler.query_map

    def test_posts_v2_query_exists(self, handler):
        """验证 posts_v2 查询被识别"""
        assert 'posts_v2' in handler.query_map

    def test_post_v2_query_exists(self, handler):
        """验证 post_v2 查询被识别"""
        assert 'post_v2' in handler.query_map

    def test_comments_v2_query_exists(self, handler):
        """验证 comments_v2 查询被识别"""
        assert 'comments_v2' in handler.query_map


class TestMutationRecognition:
    """测试 @mutation 装饰器识别"""

    def test_handler_has_mutation_map(self, handler):
        """验证 handler 正确构建了 mutation_map"""
        assert hasattr(handler, 'mutation_map')
        assert len(handler.mutation_map) > 0

    def test_create_user_v2_mutation_exists(self, handler):
        """验证 createUserV2 变更被识别"""
        assert 'createUserV2' in handler.mutation_map

    def test_create_post_v2_mutation_exists(self, handler):
        """验证 createPostV2 变更被识别"""
        assert 'createPostV2' in handler.mutation_map

    def test_create_comment_v2_mutation_exists(self, handler):
        """验证 createCommentV2 变更被识别"""
        assert 'createCommentV2' in handler.mutation_map


class TestQueryExecution:
    """测试查询执行"""

    @pytest.mark.asyncio
    async def test_query_users(self, handler):
        """测试获取所有用户"""
        result = await handler.execute('{ users_v2 { id name email role } }')

        assert result['data'] is not None
        assert 'users_v2' in result['data']
        assert len(result['data']['users_v2']) > 0
        assert result['data']['users_v2'][0]['name'] is not None

    @pytest.mark.asyncio
    async def test_query_user_by_id(self, handler):
        """测试根据 ID 获取单个用户"""
        result = await handler.execute('{ user_v2(id: 1) { id name email role } }')

        assert result['data'] is not None
        assert result['data']['user_v2']['id'] == 1
        assert result['data']['user_v2']['name'] == 'Alice'

    @pytest.mark.asyncio
    async def test_query_posts(self, handler):
        """测试获取所有文章"""
        result = await handler.execute('{ posts_v2 { id title content status } }')

        assert result['data'] is not None
        assert 'posts_v2' in result['data']
        assert len(result['data']['posts_v2']) > 0

    @pytest.mark.asyncio
    async def test_query_posts_with_filter(self, handler):
        """测试按状态筛选文章"""
        result = await handler.execute('{ posts_v2(status: "published") { id title status } }')

        assert result['data'] is not None
        for post in result['data']['posts_v2']:
            assert post['status'] == 'published'

    @pytest.mark.asyncio
    async def test_query_comments(self, handler):
        """测试获取所有评论"""
        result = await handler.execute('{ comments_v2 { id text } }')

        assert result['data'] is not None
        assert 'comments_v2' in result['data']
        assert len(result['data']['comments_v2']) > 0


class TestMutationExecution:
    """测试变更执行"""

    @pytest.mark.asyncio
    async def test_mutation_create_user(self, handler):
        """测试创建用户"""
        result = await handler.execute(
            'mutation { createUserV2(name: "TestUser", email: "test@test.com") { id name email role } }'
        )

        assert result['data'] is not None
        assert result['data']['createUserV2']['name'] == 'TestUser'
        assert result['data']['createUserV2']['email'] == 'test@test.com'
        assert result['data']['createUserV2']['role'] == 'user'  # 默认值

    @pytest.mark.asyncio
    async def test_mutation_create_user_with_role(self, handler):
        """测试创建带角色的用户"""
        result = await handler.execute(
            'mutation { createUserV2(name: "Admin", email: "admin@test.com", role: "admin") { id name role } }'
        )

        assert result['data'] is not None
        assert result['data']['createUserV2']['role'] == 'admin'

    @pytest.mark.asyncio
    async def test_mutation_create_post(self, handler):
        """测试创建文章"""
        result = await handler.execute(
            'mutation { createPostV2(title: "New Post", content: "Content", author_id: 1) { id title content author_id status } }'
        )

        assert result['data'] is not None
        assert result['data']['createPostV2']['title'] == 'New Post'
        assert result['data']['createPostV2']['author_id'] == 1
        assert result['data']['createPostV2']['status'] == 'draft'  # 默认值

    @pytest.mark.asyncio
    async def test_mutation_create_comment(self, handler):
        """测试创建评论"""
        result = await handler.execute(
            'mutation { createCommentV2(text: "Nice article!", author_id: 1, post_id: 1) { id text author_id post_id } }'
        )

        assert result['data'] is not None
        assert result['data']['createCommentV2']['text'] == 'Nice article!'
        assert result['data']['createCommentV2']['author_id'] == 1
        assert result['data']['createCommentV2']['post_id'] == 1


class TestRelationshipResolution:
    """测试关系解析"""

    @pytest.mark.asyncio
    async def test_post_author_relationship(self, handler):
        """测试文章-作者关系解析"""
        result = await handler.execute(
            '{ posts_v2 { title author { name email } } }'
        )

        assert result['data'] is not None
        posts = result['data']['posts_v2']
        assert len(posts) > 0

        # 验证每篇文章都有作者信息
        for post in posts:
            assert 'author' in post
            assert post['author'] is not None
            assert 'name' in post['author']
            assert 'email' in post['author']

    @pytest.mark.asyncio
    async def test_post_comments_relationship(self, handler):
        """测试文章-评论关系解析"""
        result = await handler.execute(
            '{ posts_v2 { title comments { text } } }'
        )

        assert result['data'] is not None
        posts = result['data']['posts_v2']
        assert len(posts) > 0

        # 第一篇文章应该有评论
        first_post = posts[0]
        if first_post.get('comments'):
            assert len(first_post['comments']) > 0
            assert 'text' in first_post['comments'][0]

    @pytest.mark.asyncio
    async def test_comment_author_relationship(self, handler):
        """测试评论-作者关系解析"""
        result = await handler.execute(
            '{ comments_v2 { text author { name } } }'
        )

        assert result['data'] is not None
        comments = result['data']['comments_v2']
        assert len(comments) > 0

        for comment in comments:
            assert 'author' in comment
            assert comment['author'] is not None
            assert 'name' in comment['author']

    @pytest.mark.asyncio
    async def test_comment_post_relationship(self, handler):
        """测试评论-文章关系解析"""
        result = await handler.execute(
            '{ comments_v2 { text post { title } } }'
        )

        assert result['data'] is not None
        comments = result['data']['comments_v2']
        assert len(comments) > 0

        for comment in comments:
            assert 'post' in comment
            assert comment['post'] is not None
            assert 'title' in comment['post']

    @pytest.mark.asyncio
    async def test_user_myposts_relationship(self, handler):
        """测试用户-文章关系解析"""
        result = await handler.execute(
            '{ users_v2 { name myposts { title status } } }'
        )

        assert result['data'] is not None
        users = result['data']['users_v2']
        assert len(users) > 0

        # Alice (id=1) 应该有文章
        alice = next((u for u in users if u['name'] == 'Alice'), None)
        if alice and alice.get('myposts'):
            assert len(alice['myposts']) > 0
            assert 'title' in alice['myposts'][0]

    @pytest.mark.asyncio
    async def test_nested_relationships(self, handler):
        """测试嵌套关系解析：文章 -> 作者 -> 文章列表"""
        result = await handler.execute(
            '{ posts_v2(limit: 2) { title author { name email myposts { title } } } }'
        )

        assert result['data'] is not None
        posts = result['data']['posts_v2']
        assert len(posts) > 0

        for post in posts:
            assert 'author' in post
            assert post['author'] is not None
            if post['author'].get('myposts'):
                # 作者的文章列表
                for author_post in post['author']['myposts']:
                    assert 'title' in author_post


class TestInputType:
    """测试 Input Type 支持"""

    @pytest.mark.asyncio
    async def test_create_user_with_input(self, handler):
        """测试使用 Input Type 创建用户"""
        result = await handler.execute(
            'mutation { createUserWithInputV2(input: {name: "InputUser", email: "input@test.com", role: "user"}) { id name email role } }'
        )

        assert result['data'] is not None
        assert result['data']['createUserWithInputV2']['name'] == 'InputUser'
        assert result['data']['createUserWithInputV2']['email'] == 'input@test.com'

    @pytest.mark.asyncio
    async def test_create_post_with_input(self, handler):
        """测试使用 Input Type 创建文章"""
        result = await handler.execute(
            'mutation { createPostWithInputV2(input: {title: "Input Post", content: "Content", author_id: 1, status: "published"}) { id title content status } }'
        )

        assert result['data'] is not None
        assert result['data']['createPostWithInputV2']['title'] == 'Input Post'
        assert result['data']['createPostWithInputV2']['status'] == 'published'


class TestErDiagramConfiguration:
    """测试 ErDiagram 配置"""

    def test_diagram_has_configs(self):
        """验证 ErDiagram 包含所有实体配置"""
        assert len(diagram_v2.configs) == 3

    def test_diagram_contains_user_entity(self):
        """验证 ErDiagram 包含 UserEntityV2"""
        entity_names = [cfg.kls.__name__ for cfg in diagram_v2.configs]
        assert 'UserEntityV2' in entity_names

    def test_diagram_contains_post_entity(self):
        """验证 ErDiagram 包含 PostEntityV2"""
        entity_names = [cfg.kls.__name__ for cfg in diagram_v2.configs]
        assert 'PostEntityV2' in entity_names

    def test_diagram_contains_comment_entity(self):
        """验证 ErDiagram 包含 CommentEntityV2"""
        entity_names = [cfg.kls.__name__ for cfg in diagram_v2.configs]
        assert 'CommentEntityV2' in entity_names

    def test_user_entity_has_relationships(self):
        """验证 UserEntityV2 在 ErDiagram 中有正确的关係配置"""
        user_cfg = next((cfg for cfg in diagram_v2.configs if cfg.kls == UserEntityV2), None)
        assert user_cfg is not None
        assert len(user_cfg.relationships) == 1
        assert user_cfg.relationships[0].default_field_name == 'myposts'

    def test_post_entity_has_relationships(self):
        """验证 PostEntityV2 在 ErDiagram 中有正确的关係配置"""
        post_cfg = next((cfg for cfg in diagram_v2.configs if cfg.kls == PostEntityV2), None)
        assert post_cfg is not None
        assert len(post_cfg.relationships) == 2  # author 和 comments


if __name__ == '__main__':
    # 运行所有测试
    pytest.main([__file__, '-v'])
