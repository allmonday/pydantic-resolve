"""
GraphQL Mutation 示例

展示如何使用 pydantic-resolve 的 @mutation 装饰器
"""

import asyncio
from demo.graphql.entities import BaseEntity
from pydantic_resolve.graphql import GraphQLHandler


async def run_mutation_examples():
    """运行各种 mutation 示例"""

    handler = GraphQLHandler(BaseEntity.get_diagram())

    print("=" * 70)
    print("GraphQL Mutation 示例")
    print("=" * 70)

    # 示例 1: 创建用户
    print("\n【示例 1】创建用户")
    print("-" * 70)
    result = await handler.execute(
        '{ createUser(name: "Alice", email: "alice@example.com", role: "admin") { id name email role } }'
    )
    print(f"Result: {result}")

    # 示例 2: 创建用户并请求关联数据（posts）
    print("\n【示例 2】创建用户并请求关联数据")
    print("-" * 70)
    result = await handler.execute(
        '''{ createUser(name: "Bob", email: "bob@test.com", role: "user") {
            id
            name
            email
            myposts {
                id
                title
                author {
                    name
                }
            }
        } }'''
    )
    print(f"Result: {result}")

    # 示例 3: 更新用户
    print("\n【示例 3】更新用户信息")
    print("-" * 70)
    result = await handler.execute(
        '{ updateUser(id: 1, name: "Alice Updated") { id name email } }'
    )
    print(f"Result: {result}")

    # 示例 4: 创建文章
    print("\n【示例 4】创建文章")
    print("-" * 70)
    result = await handler.execute(
        '''{ createPost(
            title: "My First Post",
            content: "Hello World!",
            author_id: 1,
            status: "published"
        ) {
            id
            title
            status
            author {
                id
                name
            }
        } }'''
    )
    print(f"Result: {result}")

    # 示例 5: 发布文章
    print("\n【示例 5】发布文章")
    print("-" * 70)
    result = await handler.execute(
        '{ publishPost(id: 2) { id title status } }'
    )
    print(f"Result: {result}")

    # 示例 6: 创建评论并请求完整关联数据
    print("\n【示例 6】创建评论（带完整关联数据）")
    print("-" * 70)
    result = await handler.execute(
        '''{ createComment(
            text: "Great article!",
            author_id: 1,
            post_id: 1
        ) {
            id
            text
            author {
                id
                name
                email
            }
            post {
                id
                title
                author {
                    name
                }
            }
        } }'''
    )
    print(f"Result: {result}")

    # 示例 7: 删除操作
    print("\n【示例 7】删除评论")
    print("-" * 70)
    result = await handler.execute(
        '{ deleteComment(id: 1) }'
    )
    print(f"Result: {result}")

    # 示例 8: 多个 mutation 顺序执行
    print("\n【示例 8】多个 mutation 顺序执行")
    print("-" * 70)
    result = await handler.execute(
        '''{
            user1: createUser(name: "User 1", email: "user1@test.com", role: "user") { id name }
            user2: createUser(name: "User 2", email: "user2@test.com", role: "user") { id name }
            post1: createPost(title: "Post 1", content: "Content 1", author_id: 1) { id title }
            post2: createPost(title: "Post 2", content: "Content 2", author_id: 2) { id title }
        }'''
    )
    print(f"Result: {result}")

    # 示例 9: 联合使用 query 和 mutation
    print("\n【示例 9】Query + Mutation 组合")
    print("-" * 70)
    print("Step 1: 创建用户")
    result = await handler.execute(
        '{ createUser(name: "Charlie", email: "charlie@test.com", role: "user") { id name } }'
    )
    print(f"Created: {result}")

    print("\nStep 2: 查询所有用户")
    result = await handler.execute(
        '{ users(limit: 10, offset: 0) { id name email role } }'
    )
    print(f"All users: {result}")

    # 示例 10: 错误处理
    print("\n【示例 10】错误处理 - 尝试更新不存在的用户")
    print("-" * 70)
    result = await handler.execute(
        '{ updateUser(id: 9999, name: "Ghost") { id name } }'
    )
    print(f"Result: {result}")


async def show_introspection():
    """展示 mutation 的 introspection 信息"""
    print("\n" + "=" * 70)
    print("Mutation Introspection")
    print("=" * 70)

    handler = GraphQLHandler(BaseEntity.get_diagram())

    # 查询所有 mutations
    result = await handler.execute(
        '{ __schema { mutationType { name fields { name description args { name type { name } } } } } }'
    )

    if result.get("data"):
        mutation_type = result["data"]["__schema"].get("mutationType")
        if mutation_type:
            print("\n可用的 Mutations:")
            for field in mutation_type.get("fields", []):
                name = field.get("name")
                description = field.get("description", "")
                args = field.get("args", [])
                arg_str = ", ".join([
                    f"{a['name']}: {a['type']['name']}"
                    for a in args if a['name'] != 'cls'
                ])
                print(f"  - {name}({arg_str}): {description}")


if __name__ == "__main__":
    # 运行所有示例
    asyncio.run(run_mutation_examples())

    # 展示 introspection
    asyncio.run(show_introspection())

    print("\n" + "=" * 70)
    print("所有示例运行完成！")
    print("=" * 70)
