"""
测试 GraphQL Demo 功能
"""

import asyncio
import json
from demo.graphql.app import BaseEntity
from pydantic_resolve import config_global_resolver
from pydantic_resolve.graphql import GraphQLHandler


async def run_queries():
    """测试各种 GraphQL 查询"""

    # 配置全局 resolver
    config_global_resolver(BaseEntity.get_diagram())

    # 创建 GraphQL handler
    handler = GraphQLHandler(BaseEntity.get_diagram())

    print("=" * 60)
    print("GraphQL Demo 查询测试")
    print("=" * 60)

    # 测试 1: 获取所有用户
    print("\n1. 获取所有用户:")
    result = await handler.execute("{ users { id name email role } }")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 测试 2: 获取分页用户
    print("\n2. 获取分页用户 (limit=2, offset=1):")
    result = await handler.execute("{ users(limit: 2, offset: 1) { id name email } }")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 测试 3: 获取单个用户
    print("\n3. 获取单个用户 (id=1):")
    result = await handler.execute("{ user(id: 1) { id name email role } }")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 测试 4: 获取用户及其文章
    print("\n4. 获取用户及其文章:")
    result = await handler.execute("{ user(id: 1) { id name email posts { title content status } } }")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 测试 5: 获取所有文章
    print("\n5. 获取所有文章:")
    result = await handler.execute("{ posts { id title content status } }")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 测试 6: 获取已发布的文章
    print("\n6. 获取已发布的文章:")
    result = await handler.execute('{ posts(status: "published") { id title content } }')
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 测试 7: 获取文章及其作者
    print("\n7. 获取文章及其作者:")
    result = await handler.execute("{ posts { title content author { name email role } } }")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 测试 8: 获取评论及作者和文章
    print("\n8. 获取评论及作者和文章:")
    result = await handler.execute("{ comments { text author { name email } post { title } } }")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 测试 9: 获取管理员
    print("\n9. 获取所有管理员:")
    result = await handler.execute("{ admins { id name email } }")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 测试 10: 获取单个文章及完整信息
    print("\n10. 获取单个文章及完整信息:")
    result = await handler.execute("{ post(id: 1) { title content author { name email } comments { text author { name } } } }")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 测试 11: 查询错误的 ID
    print("\n11. 查询不存在的用户 (错误处理):")
    result = await handler.execute("{ user(id: 999) { id name } }")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 测试 12: 无效查询
    print("\n12. 无效查询 (错误处理):")
    result = await handler.execute("{ non_existent { id } }")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_queries())
