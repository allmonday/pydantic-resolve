"""
快速测试所有的 Mutations
"""

import asyncio
from demo.graphql.entities import BaseEntity
from pydantic_resolve.graphql import GraphQLHandler


async def test_all_mutations():
    """快速测试所有 10 个 mutations"""
    handler = GraphQLHandler(BaseEntity.get_diagram())

    print("🧪 测试所有 Mutations")
    print("=" * 70)

    tests = [
        ("创建用户", '{ createUser(name: "Test User", email: "test@test.com", role: "user") { id name email role } }'),
        ("更新用户", '{ updateUser(id: 1, name: "Updated") { id name } }'),
        ("创建文章", '{ createPost(title: "Test Post", content: "Test", author_id: 1, status: "draft") { id title status } }'),
        ("发布文章", '{ publishPost(id: 2) { id title status } }'),
        ("创建评论", '{ createComment(text: "Test comment", author_id: 1, post_id: 1) { id text } }'),
    ]

    passed = 0
    failed = 0

    for name, query in tests:
        try:
            result = await handler.execute(query)
            if result.get("data") and not result.get("errors"):
                print(f"✅ {name}: 成功")
                passed += 1
            else:
                print(f"❌ {name}: 失败 - {result.get('errors')}")
                failed += 1
        except Exception as e:
            print(f"❌ {name}: 异常 - {e}")
            failed += 1

    print("\n" + "=" * 70)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 70)

    # 显示统计信息
    print("\n📊 Mutation 统计:")
    print(f"   总 mutations: {len(handler.mutation_map)}")
    print(f"   UserEntity: {len([m for m in handler.mutation_map if 'user' in m.lower()])}")
    print(f"   PostEntity: {len([m for m in handler.mutation_map if 'post' in m.lower()])}")
    print(f"   CommentEntity: {len([m for m in handler.mutation_map if 'comment' in m.lower()])}")


if __name__ == "__main__":
    asyncio.run(test_all_mutations())
