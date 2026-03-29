"""
测试 QueryConfig 和 MutationConfig 配置化功能
"""

import pytest
from typing import Optional, List
from pydantic import BaseModel

from pydantic_resolve import (
    ErDiagram,
    Entity,
    Relationship,
    QueryConfig,
    MutationConfig,
    query,
    mutation,
)
from pydantic_resolve.graphql import SchemaBuilder


# ========== 基础实体定义（不含方法）==========
class UserEntityForConfig(BaseModel):
    id: int
    name: str
    email: str


class PostEntityForConfig(BaseModel):
    id: int
    title: str
    author_id: int


class CreatePostInput(BaseModel):
    title: str
    author_id: int


# ========== 外部定义的方法（无需 cls 参数）==========
async def get_all_users(limit: int = 10) -> List[UserEntityForConfig]:
    """获取所有用户"""
    return [
        UserEntityForConfig(id=1, name="Alice", email="alice@example.com"),
        UserEntityForConfig(id=2, name="Bob", email="bob@example.com"),
    ][:limit]


async def get_user_by_id(user_id: int) -> Optional[UserEntityForConfig]:
    """根据 ID 获取用户"""
    users = {
        1: UserEntityForConfig(id=1, name="Alice", email="alice@example.com"),
        2: UserEntityForConfig(id=2, name="Bob", email="bob@example.com"),
    }
    return users.get(user_id)


async def get_all_posts() -> List[PostEntityForConfig]:
    """获取所有文章"""
    return [
        PostEntityForConfig(id=1, title="First Post", author_id=1),
        PostEntityForConfig(id=2, title="Second Post", author_id=2),
    ]


async def create_post(input: CreatePostInput) -> PostEntityForConfig:
    """创建文章"""
    return PostEntityForConfig(
        id=3,
        title=input.title,
        author_id=input.author_id
    )


async def delete_post(post_id: int) -> bool:
    """删除文章"""
    return True


# ========== 测试类 ==========
class TestQueryMutationConfig:
    """测试 QueryConfig 和 MutationConfig 基本功能"""

    def test_query_config_basic(self):
        """测试 QueryConfig 基本属性"""
        config = QueryConfig(
            method=get_all_users,
            name='users',
            description='获取所有用户'
        )
        assert config.method == get_all_users
        assert config.name == 'users'
        assert config.description == '获取所有用户'

    def test_mutation_config_basic(self):
        """测试 MutationConfig 基本属性"""
        config = MutationConfig(
            method=create_post,
            name='createPost',
            description='创建文章'
        )
        assert config.method == create_post
        assert config.name == 'createPost'
        assert config.description == '创建文章'

    def test_config_with_defaults(self):
        """测试配置的默认值"""
        config = QueryConfig(method=get_all_users)
        assert config.name is None
        assert config.description is None


class TestErDiagramBinding:
    """测试 ErDiagram 动态绑定功能"""

    def test_bind_query_to_entity(self):
        """测试将 Query 方法绑定到 Entity"""
        _diagram = ErDiagram(configs=[
            Entity(
                kls=UserEntityForConfig,
                relationships=[],
                queries=[
                    QueryConfig(method=get_all_users, name='users'),
                    QueryConfig(method=get_user_by_id, name='userById'),
                ]
            )
        ])

        # 验证方法已被绑定
        assert hasattr(UserEntityForConfig, 'get_all_users')
        assert hasattr(UserEntityForConfig, 'get_user_by_id')

        # 验证是 classmethod
        assert isinstance(UserEntityForConfig.__dict__['get_all_users'], classmethod)
        assert isinstance(UserEntityForConfig.__dict__['get_user_by_id'], classmethod)

    def test_bind_mutation_to_entity(self):
        """测试将 Mutation 方法绑定到 Entity"""
        _diagram = ErDiagram(configs=[
            Entity(
                kls=PostEntityForConfig,
                relationships=[],
                mutations=[
                    MutationConfig(method=create_post, name='createPost'),
                    MutationConfig(method=delete_post, name='deletePost'),
                ]
            )
        ])

        # 验证方法已被绑定
        assert hasattr(PostEntityForConfig, 'create_post')
        assert hasattr(PostEntityForConfig, 'delete_post')

        # 验证是 classmethod
        assert isinstance(PostEntityForConfig.__dict__['create_post'], classmethod)
        assert isinstance(PostEntityForConfig.__dict__['delete_post'], classmethod)

    def test_wrapper_ignores_cls_parameter(self):
        """测试包装器自动忽略 cls 参数"""
        _diagram = ErDiagram(configs=[
            Entity(
                kls=UserEntityForConfig,
                relationships=[],
                queries=[QueryConfig(method=get_all_users, name='users')]
            )
        ])

        # 获取绑定的方法
        bound_method = UserEntityForConfig.get_all_users

        # 验证元数据被正确设置
        actual_func = bound_method.__func__
        assert hasattr(actual_func, '_pydantic_resolve_query')
        assert actual_func._pydantic_resolve_query is True
        assert actual_func._pydantic_resolve_query_name == 'users'

    def test_method_callable_without_cls(self):
        """测试绑定后的方法可以正常调用（无需传递 cls）"""
        _diagram = ErDiagram(configs=[
            Entity(
                kls=UserEntityForConfig,
                relationships=[],
                queries=[QueryConfig(method=get_all_users, name='users')]
            )
        ])

        # 作为 classmethod 调用，不需要实例
        # 这验证了包装器正确地忽略了 cls 参数
        import asyncio
        result = asyncio.run(UserEntityForConfig.get_all_users(limit=1))
        assert len(result) == 1
        assert result[0].name == "Alice"


# ========== 混合使用测试用的实体（模块级别，避免动态类导致的 teardown 问题）==========
class UserWithDecorator(BaseModel):
    id: int
    name: str

    @query
    async def get_all(cls, limit: int = 10) -> List['UserWithDecorator']:
        """获取所有用户"""
        return []


class PostWithConfig(BaseModel):
    id: int
    title: str


async def _get_posts_for_mixed_test() -> List[PostWithConfig]:
    return []


class TestSchemaBuilderCompatibility:
    """测试 SchemaBuilder 与配置化方法的兼容性"""

    def test_schema_generation_with_config(self):
        """测试 SchemaBuilder 能正确识别配置化的方法"""
        diagram = ErDiagram(configs=[
            Entity(
                kls=UserEntityForConfig,
                relationships=[],
                queries=[QueryConfig(method=get_all_users, name='users')]
            ),
            Entity(
                kls=PostEntityForConfig,
                relationships=[],
                queries=[QueryConfig(method=get_all_posts)],
                mutations=[MutationConfig(method=create_post, name='createPost')]
            )
        ])

        builder = SchemaBuilder(diagram)
        schema = builder.build_schema()

        # 验证 Query 类型包含配置的方法 (新命名风格)
        assert 'userEntityForConfigGetAllUsers(limit: Int): [UserEntityForConfig!]' in schema
        assert 'postEntityForConfigGetAllPosts: [PostEntityForConfig!]' in schema

        # 验证 Mutation 类型包含配置的方法
        assert 'postEntityForConfigCreatePost(input: CreatePostInput!): PostEntityForConfig!' in schema

    def test_mixed_decorator_and_config(self):
        """测试装饰器和配置混合使用"""
        diagram = ErDiagram(configs=[
            Entity(kls=UserWithDecorator, relationships=[]),
            Entity(
                kls=PostWithConfig,
                relationships=[],
                queries=[QueryConfig(method=_get_posts_for_mixed_test, name='posts')]
            )
        ])

        builder = SchemaBuilder(diagram)
        schema = builder.build_schema()

        # 验证两种方式都能被正确识别 (新命名风格)
        assert 'userWithDecoratorGetAll(limit: Int): [UserWithDecorator!]' in schema
        assert 'postWithConfigGetPostsForMixedTest: [PostWithConfig!]' in schema


# ========== 循环引用测试用的实体（模块级别，避免动态类导致的 teardown 问题）==========
class AuthorEntity(BaseModel):
    id: int
    name: str


class BookEntity(BaseModel):
    id: int
    title: str
    author_id: int


async def _get_authors() -> List[AuthorEntity]:
    return [AuthorEntity(id=1, name="Author 1")]


async def _get_books_by_author(author_id: int) -> List[BookEntity]:
    return [BookEntity(id=1, title="Book 1", author_id=author_id)]


class TestCircularReferenceScenario:
    """测试循环引用场景（配置化的主要用例）"""

    def test_circular_reference_without_import_issues(self):
        """测试循环引用场景下不会产生导入问题

        这是配置化的主要用例：Entity A 和 B 相互引用，
        但方法定义在外部，避免了循环导入。
        """
        # 配置 ErDiagram
        diagram = ErDiagram(configs=[
            Entity(
                kls=AuthorEntity,
                relationships=[Relationship(field='id', target_kls=list[BookEntity], field_name='books')],
                queries=[QueryConfig(method=_get_authors, name='authors')]
            ),
            Entity(
                kls=BookEntity,
                relationships=[Relationship(field='author_id', target_kls=AuthorEntity, field_name='author')],
                queries=[QueryConfig(method=_get_books_by_author, name='booksByAuthor')]
            )
        ])

        # 验证 Schema 生成成功
        builder = SchemaBuilder(diagram)
        schema = builder.build_schema()

        assert 'type AuthorEntity' in schema
        assert 'type BookEntity' in schema
        # 新命名风格
        assert 'authorEntityGetAuthors: [AuthorEntity!]' in schema
        assert 'bookEntityGetBooksByAuthor(author_id: Int!): [BookEntity!]' in schema


class TestEntityDefaultValues:
    """测试 Entity 的默认值"""

    def test_entity_with_empty_lists(self):
        """测试 Entity 的 relationships/queries/mutations 默认为空列表"""
        entity = Entity(kls=UserEntityForConfig)
        assert entity.relationships == []
        assert entity.queries == []
        assert entity.mutations == []

    def test_entity_with_only_queries(self):
        """测试只有 queries 的 Entity"""
        entity = Entity(
            kls=UserEntityForConfig,
            queries=[QueryConfig(method=get_all_users)]
        )
        assert entity.relationships == []
        assert len(entity.queries) == 1
        assert entity.mutations == []


# ========== 冲突检测测试用的独立实体 ==========
class UserWithDecoratorForConflict(BaseModel):
    """用于测试冲突检测的实体，带装饰器方法"""
    id: int
    name: str

    @query
    async def get_all(cls, limit: int = 10) -> List['UserWithDecoratorForConflict']:
        """获取所有用户"""
        return []


class EntityWithMutationForConflict(BaseModel):
    """用于测试冲突检测的实体，带装饰器方法"""
    id: int

    @mutation
    async def delete_entity(cls, id: int) -> bool:
        """删除实体"""
        return True


class TestMethodConflictDetection:
    """测试方法冲突检测"""

    def test_query_conflict_with_decorator(self):
        """测试 QueryConfig 与装饰器定义的方法冲突时抛出异常"""
        # UserWithDecoratorForConflict 已通过 @query 装饰器定义了 get_all 方法
        # 尝试用 QueryConfig 绑定同名方法应该抛出异常

        # 方法名必须与现有方法名相同才能触发冲突检测
        async def get_all(cls, limit: int = 10) -> List[UserWithDecoratorForConflict]:
            return []

        with pytest.raises(ValueError, match="Method 'get_all' already exists in UserWithDecoratorForConflict"):
            ErDiagram(configs=[
                Entity(
                    kls=UserWithDecoratorForConflict,
                    relationships=[],
                    queries=[QueryConfig(method=get_all, name='users')]
                )
            ])

    def test_mutation_conflict_with_decorator(self):
        """测试 MutationConfig 与装饰器定义的方法冲突时抛出异常"""
        # 方法名必须与现有方法名相同才能触发冲突检测
        async def delete_entity(cls, id: int) -> bool:
            """删除实体"""
            return False

        with pytest.raises(ValueError, match="Method 'delete_entity' already exists in EntityWithMutationForConflict"):
            ErDiagram(configs=[
                Entity(
                    kls=EntityWithMutationForConflict,
                    relationships=[],
                    mutations=[MutationConfig(method=delete_entity, name='delete')]
                )
            ])
