"""
GraphQL Demo FastAPI 应用
提供可查询的 GraphQL endpoint
"""

from fastapi import FastAPI, APIRouter
from fastapi.responses import PlainTextResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
from pydantic_resolve import config_global_resolver
from pydantic_resolve import GraphQLHandler, SchemaBuilder

# from demo.graphql.entities import BaseEntity
from demo.graphql.entities_v2 import diagram_v2

# diagram = BaseEntity.get_diagram()  # 获取 V1 实体图
diagram = diagram_v2

# 创建 FastAPI 应用
app = FastAPI(diagram = diagram,  # 获取 V1 实体图
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

# 创建 GraphQL handler 和 schema builder
handler = GraphQLHandler(diagram, enable_from_attribute_in_type_adapter=True)
schema_builder = SchemaBuilder(diagram)

# 定义 GraphQL 请求模型
class GraphQLRequest(BaseModel):
    query: str
    variables: Optional[Dict[str, Any]] = None
    operation_name: Optional[str] = None


# GraphiQL Playground HTML
GRAPHIQL_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>GraphiQL - Pydantic Resolve Demo</title>
  <style>
    body { margin: 0; }
    #graphiql { height: 100dvh; }
    .loading {
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 2rem;
    }
  </style>
  <link rel="stylesheet" href="https://esm.sh/graphiql/dist/style.css" />
  <link rel="stylesheet" href="https://esm.sh/@graphiql/plugin-explorer/dist/style.css" />
  <script type="importmap">
    {
      "imports": {
        "react": "https://esm.sh/react@19.1.0",
        "react/jsx-runtime": "https://esm.sh/react@19.1.0/jsx-runtime",
        "react-dom": "https://esm.sh/react-dom@19.1.0",
        "react-dom/client": "https://esm.sh/react-dom@19.1.0/client",
        "@emotion/is-prop-valid": "data:text/javascript,",
        "graphiql": "https://esm.sh/graphiql?standalone&external=react,react-dom,@graphiql/react,graphql",
        "graphiql/": "https://esm.sh/graphiql/",
        "@graphiql/plugin-explorer": "https://esm.sh/@graphiql/plugin-explorer?standalone&external=react,@graphiql/react,graphql",
        "@graphiql/react": "https://esm.sh/@graphiql/react?standalone&external=react,react-dom,graphql,@emotion/is-prop-valid",
        "@graphiql/toolkit": "https://esm.sh/@graphiql/toolkit?standalone&external=graphql",
        "graphql": "https://esm.sh/graphql@16.11.0"
      }
    }
  </script>
</head>
<body>
  <div id="graphiql">
    <div class="loading">Loading…</div>
  </div>
  <script type="module">
    import React from 'react';
    import ReactDOM from 'react-dom/client';
    import { GraphiQL, HISTORY_PLUGIN } from 'graphiql';
    import { createGraphiQLFetcher } from '@graphiql/toolkit';
    import { explorerPlugin } from '@graphiql/plugin-explorer';

    const fetcher = createGraphiQLFetcher({ url: '/graphql' });
    const plugins = [HISTORY_PLUGIN, explorerPlugin()];

    function App() {
      return React.createElement(GraphiQL, {
        fetcher: fetcher,
        plugins: plugins,
      });
    }

    const container = document.getElementById('graphiql');
    const root = ReactDOM.createRoot(container);
    root.render(React.createElement(App));
  </script>
</body>
</html>
"""


# 创建 GraphQL 路由
graphql_router = APIRouter()


@graphql_router.get("/graphql", response_class=HTMLResponse)
async def graphiql_playground():
    """GraphiQL 交互式查询界面"""
    return GRAPHIQL_HTML


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
