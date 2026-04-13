"""
GraphQL Demo FastAPI 应用
提供可查询的 GraphQL endpoint
"""

from fastapi import FastAPI, APIRouter, Request
from fastapi.responses import PlainTextResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from pydantic_resolve import config_global_resolver
from pydantic_resolve import GraphQLHandler, SchemaBuilder

from demo.graphql.entities_v3 import diagram_v3, init_db_v3

diagram = diagram_v3

# 创建 FastAPI 应用
app = FastAPI(diagram=diagram,
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
config_global_resolver(diagram)


@app.on_event("startup")
async def startup():
    """Initialize database tables and seed data."""
    await init_db_v3()

# 创建 GraphQL handler 和 schema builder
handler = GraphQLHandler(diagram, enable_from_attribute_in_type_adapter=True)
schema_builder = SchemaBuilder(diagram)

# 定义 GraphQL 请求模型
class GraphQLRequest(BaseModel):
    query: str
    operationName: Optional[str] = None


# GraphiQL Playground HTML (provided by library)
GRAPHIQL_HTML = handler.get_graphiql_html(title="GraphiQL - Pydantic Resolve Demo")


# 创建 GraphQL 路由
graphql_router = APIRouter()


@graphql_router.get("/graphql", response_class=HTMLResponse)
async def graphiql_playground():
    """GraphiQL 交互式查询界面"""
    return GRAPHIQL_HTML


@graphql_router.post("/graphql")
async def graphql_endpoint(req: GraphQLRequest, request: Request):
    """GraphQL query endpoint with request context."""
    # Extract user context from JWT or session.
    # This is a simplified example — in production, use proper JWT decoding.
    auth_header = request.headers.get("Authorization", "")
    user_id = None
    if auth_header.startswith("Bearer "):
        # Placeholder: decode JWT and extract user_id
        # token = auth_header[7:]
        # payload = jwt.decode(token, ...)
        # user_id = payload.get("user_id")
        user_id = 1  # placeholder

    context = {"user_id": user_id} if user_id else None

    result = await handler.execute(
        query=req.query,
        context=context,
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
            "playground": "/graphql (GET - GraphiQL UI)",
            "graphql": "/graphql (POST - Query endpoint)",
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
