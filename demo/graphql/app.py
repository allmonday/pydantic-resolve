"""
GraphQL Demo FastAPI 应用
提供可查询的 GraphQL endpoint
"""

from fastapi import FastAPI, APIRouter
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
from pydantic_resolve import config_global_resolver
from pydantic_resolve import GraphQLHandler, SchemaBuilder

from demo.graphql.entities import BaseEntity


# 创建 FastAPI 应用
app = FastAPI(
    title="Pydantic Resolve GraphQL Demo",
    description="演示 pydantic-resolve 的 GraphQL 查询功能",
    version="1.0.0"
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置全局 resolver
config_global_resolver(BaseEntity.get_diagram())

# 创建 GraphQL handler 和 schema builder
handler = GraphQLHandler(BaseEntity.get_diagram(), enable_from_attribute_in_type_adapter=True)
schema_builder = SchemaBuilder(BaseEntity.get_diagram())

# 定义 GraphQL 请求模型
class GraphQLRequest(BaseModel):
    query: str
    variables: Optional[Dict[str, Any]] = None
    operation_name: Optional[str] = None

# 创建 GraphQL 路由
graphql_router = APIRouter()

@graphql_router.post("/graphql")
async def graphql_endpoint(req: GraphQLRequest):
    """GraphQL 查询端点"""
    result = await handler.execute(
        query=req.query,
        variables=req.variables,
        operation_name=req.operation_name
    )
    return result

@graphql_router.get("/schema", response_class=None)
async def graphql_schema():
    """GraphQL Schema 端点（返回 SDL 格式）"""
    schema_sdl = schema_builder.build_schema()
    return PlainTextResponse(
        content=schema_sdl,
        media_type="text/plain; charset=utf-8"
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
