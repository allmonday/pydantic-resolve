"""
展示所有可用的 Mutations
"""

import asyncio
from demo.graphql.entities import BaseEntity
from pydantic_resolve.graphql import GraphQLHandler


async def show_mutations():
    """显示所有可用的 mutation 方法"""
    handler = GraphQLHandler(BaseEntity.get_diagram())

    print("=" * 70)
    print("pydantic-resolve GraphQL Mutations")
    print("=" * 70)

    # 从 mutation_map 直接读取
    print("\n可用的 Mutations:")
    print("-" * 70)

    for mutation_name, (entity, method) in sorted(handler.mutation_map.items()):
        print(f"\n{mutation_name}")
        print(f"  实体: {entity.__name__}")
        print(f"  方法: {method.__name__}")

        # 获取方法签名
        import inspect
        sig = inspect.signature(method)

        # 获取参数
        params = []
        for param_name, param in sig.parameters.items():
            if param_name == 'cls':
                continue
            param_type = param.annotation if param.annotation != inspect.Parameter.empty else "Any"
            default = f" = {param.default}" if param.default != inspect.Parameter.empty else ""
            params.append(f"{param_name}: {param_type}{default}")

        print(f"  参数: {', '.join(params)}")


if __name__ == "__main__":
    asyncio.run(show_mutations())
