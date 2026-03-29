"""
测试 field_name 命名冲突检测
"""

import pytest
from pydantic import BaseModel
from pydantic_resolve import base_entity, Relationship


def test_scalar_field_conflict():
    """测试标量字段与关系字段的冲突检测"""
    BaseEntity = base_entity()

    # 需要先定义 PostEntity
    class PostEntity(BaseModel, BaseEntity):
        id: int

    class UserEntity(BaseModel, BaseEntity):
        posts: int  # 标量字段

        __relationships__ = [
            Relationship(
                field='id',
                target_kls=list[PostEntity],  # 使用类引用，不是字符串
                field_name='posts'  # 冲突！
            )
        ]

    # 调用 get_diagram() 时才会触发验证
    with pytest.raises(ValueError) as exc_info:
        BaseEntity.get_diagram()

    error_msg = str(exc_info.value)
    assert "Field name conflict" in error_msg
    assert "posts" in error_msg
    assert "conflicts with scalar field" in error_msg
    assert "UserEntity" in error_msg


def test_duplicate_relationship_field():
    """测试多个关系使用相同的 field_name"""
    BaseEntity = base_entity()

    # 需要先定义 UserEntity
    class UserEntity(BaseModel, BaseEntity):
        id: int

    class PostEntity(BaseModel, BaseEntity):
        __relationships__ = [
            Relationship(
                field='author_id',
                target_kls=UserEntity,
                field_name='author'
            ),
            Relationship(
                field='reviewer_id',
                target_kls=UserEntity,
                field_name='author'  # 重复！
            )
        ]

    # 调用 get_diagram() 时才会触发验证
    with pytest.raises(ValueError) as exc_info:
        BaseEntity.get_diagram()

    error_msg = str(exc_info.value)
    assert "Duplicate field_name" in error_msg
    assert "author" in error_msg
    assert "PostEntity" in error_msg


def test_inheritance_conflict():
    """测试继承中的字段冲突"""
    BaseEntity = base_entity()

    # 需要先定义 OwnerEntity
    class OwnerEntity(BaseModel, BaseEntity):
        id: int

    # 注意：Base 必须是第一个父类以避免 MRO 问题
    class UserEntity(BaseModel, BaseEntity):
        owner: str  # 父类字段

        __relationships__ = [
            Relationship(
                field='id',
                target_kls=OwnerEntity,
                field_name='owner'  # 与自己的标量字段冲突！
            )
        ]

    # 调用 get_diagram() 时才会触发验证
    with pytest.raises(ValueError) as exc_info:
        BaseEntity.get_diagram()

    error_msg = str(exc_info.value)
    assert "Field name conflict" in error_msg
    assert "owner" in error_msg
    assert "conflicts with scalar field" in error_msg
    assert "UserEntity" in error_msg


def test_no_conflict_works():
    """测试无冲突的情况正常工作"""
    BaseEntity = base_entity()

    class PostEntity(BaseModel, BaseEntity):
        id: int

    # 应该不抛出异常
    class UserEntity(BaseModel, BaseEntity):
        post_count: int  # 不同的字段名

        __relationships__ = [
            Relationship(
                field='id',
                target_kls=list[PostEntity],
                field_name='posts'  # 不冲突
            )
        ]

    # 验证实体正常创建
    assert UserEntity.__name__ == "UserEntity"

    # 验证 get_diagram() 正常工作
    er_diagram = BaseEntity.get_diagram()
    assert er_diagram is not None


def test_schema_builder_validation():
    """测试 SchemaBuilder 的运行时验证"""
    from pydantic_resolve.graphql.schema_builder import SchemaBuilder

    # 创建一个新的 Base，避免与其他测试冲突
    TestBase = base_entity()

    # RelatedEntity 需要先定义
    class RelatedEntity(BaseModel, TestBase):
        id: int

    # 创建一个正常的实体
    class NormalEntity(BaseModel, TestBase):
        id: int
        name: str

        __relationships__ = [
            Relationship(
                field='id',
                target_kls=list[RelatedEntity],
                field_name='related_items'  # 不冲突
            )
        ]

    er_diagram = TestBase.get_diagram()

    # 启用验证时应该不抛异常（无冲突）
    builder = SchemaBuilder(er_diagram, validate_conflicts=True)
    schema = builder.build_schema()
    assert "type NormalEntity" in schema

    # 禁用验证时也不抛异常
    builder = SchemaBuilder(er_diagram, validate_conflicts=False)
    schema = builder.build_schema()
    assert "type NormalEntity" in schema


def test_multiple_relationships_different_names():
    """测试多个关系使用不同的字段名（正常情况）"""
    BaseEntity = base_entity()

    # 需要先定义 UserEntity
    class UserEntity(BaseModel, BaseEntity):
        id: int

    # 应该不抛出异常
    class PostEntity(BaseModel, BaseEntity):
        __relationships__ = [
            Relationship(
                field='author_id',
                target_kls=UserEntity,
                field_name='author'
            ),
            Relationship(
                field='reviewer_id',
                target_kls=UserEntity,
                field_name='reviewer'  # 不同的名字，不冲突
            )
        ]

    # 调用 get_diagram() 验证不会抛出异常
    BaseEntity.get_diagram()
    assert PostEntity.__name__ == "PostEntity"


def test_no_field_name_validation_skipped():
    """测试缺少 field_name 应该抛出验证错误"""
    BaseEntity = base_entity()

    # 需要先定义 PostEntity
    class PostEntity(BaseModel, BaseEntity):
        id: int

    # Relationship 定义时就会抛出验证错误（field_name 是必填项）
    with pytest.raises(Exception) as exc_info:
        class UserEntity(BaseModel, BaseEntity):
            posts: int  # 标量字段

            __relationships__ = [
                Relationship(
                    field='id',
                    # field_name is intentionally missing to test validation
                    target_kls=list[PostEntity]
                )
            ]

    assert "field_name" in str(exc_info.value).lower() or "required" in str(exc_info.value).lower()


def test_error_message_quality():
    """测试错误消息的质量和可操作性"""
    BaseEntity = base_entity()

    # 需要先定义 StatusEntity
    class StatusEntity(BaseModel, BaseEntity):
        id: int

    class TestEntity(BaseModel, BaseEntity):
        status: str

        __relationships__ = [
            Relationship(
                field='status_id',
                target_kls=StatusEntity,
                field_name='status'
            )
        ]

    # 调用 get_diagram() 时触发验证
    with pytest.raises(ValueError) as exc_info:
        BaseEntity.get_diagram()

    error_msg = str(exc_info.value)

    # 验证错误消息包含关键信息
    assert "TestEntity" in error_msg  # 实体名
    assert "status" in error_msg  # 字段名
    assert "conflicts with scalar field" in error_msg  # 冲突类型
    assert "status_id" in error_msg  # 关系的 field 属性
    assert "StatusEntity" in error_msg  # 目标类
