"""
快速测试 entities.py (v1) 的 Mutations —— 分组布局

每个 mutation 现在挂在 ``{Entity}Mutation`` 组下：
``mutation { UserEntity { create_user(...) {...} } }``
"""

import pytest

from demo.graphql.entities import BaseEntity
from pydantic_resolve import config_global_resolver
from pydantic_resolve.graphql import GraphQLHandler


@pytest.fixture
def handler():
    config_global_resolver(BaseEntity.get_diagram())
    return GraphQLHandler(BaseEntity.get_diagram())


@pytest.mark.asyncio
async def test_all_mutations(handler):
    """分组布局下执行 v1 的代表性 mutations。"""
    cases = [
        ("创建用户", 'mutation { UserEntity { create_user(name: "Test User", email: "test@test.com", role: "user") { id name email role } } }'),
        ("更新用户", 'mutation { UserEntity { update_user(id: 1, name: "Updated") { id name } } }'),
        ("创建文章", 'mutation { PostEntity { create_post(title: "Test Post", content: "Test", author_id: 1, status: "draft") { id title status } } }'),
        ("发布文章", 'mutation { PostEntity { publish_post(id: 2) { id title status } } }'),
        ("创建评论", 'mutation { CommentEntity { create_comment(text: "Test comment", author_id: 1, post_id: 1) { id text } } }'),
    ]

    for name, query in cases:
        result = await handler.execute(query)
        assert result.get("data") is not None, f"{name} 失败: {result.get('errors')}"
        assert not result.get("errors"), f"{name} 失败: {result['errors']}"


if __name__ == "__main__":
    import asyncio

    async def run():
        config_global_resolver(BaseEntity.get_diagram())
        h = GraphQLHandler(BaseEntity.get_diagram())
        for name, query in [
            ("创建用户", 'mutation { UserEntity { create_user(name: "Test User", email: "test@test.com", role: "user") { id name email role } } }'),
            ("创建文章", 'mutation { PostEntity { create_post(title: "Test Post", content: "Test", author_id: 1, status: "draft") { id title status } } }'),
        ]:
            result = await h.execute(query)
            print(f"{'✅' if result.get('data') and not result.get('errors') else '❌'} {name}")

    asyncio.run(run())
