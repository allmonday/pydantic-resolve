"""
GraphQL Demo FastAPI 应用
提供可查询的 GraphQL endpoint
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic_resolve import config_global_resolver
from pydantic_resolve.graphql import create_graphql_route

from demo.graphql.entities import BaseEntity


# 创建 FastAPI 应用
app = FastAPI(
    title="Pydantic Resolve GraphQL Demo",
    description="演示 pydantic-resolve 的 GraphQL 查询功能",
    version="1.0.0"
)

# 添加 CORS 中间件以支持 GraphiQL 等客户端
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源（开发环境）
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有请求头
)

# 配置全局 resolver
config_global_resolver(BaseEntity.get_diagram())

# 创建 GraphQL 路由
graphql_router = create_graphql_route(
    er_diagram=BaseEntity.get_diagram(),
    path="/graphql"
)

# 挂载路由
app.include_router(graphql_router)


@app.get("/")
async def root():
    """根路径 - 返回使用说明"""
    return {
        "message": "GraphQL Demo Server",
        "endpoints": {
            "graphql": "/graphql",
            "schema": "/schema",
            "docs": "/docs"
        },
        "example_queries": [
            "获取所有用户",
            "获取单个用户及其文章",
            "获取文章和作者信息",
            "获取评论和作者"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# 开发提示: 推荐使用以下命令启动以支持热重载:
# uv run uvicorn demo.graphql.app:app --reload
