# GraphQL 框架集成指南

## 概述

`pydantic-resolve` 提供了框架无关的 `GraphQLHandler` 核心来执行 GraphQL 查询。本指南展示如何将其集成到各种 Web 框架中。

## GraphQLHandler API

### 构造函数

```python
from pydantic_resolve.graphql import GraphQLHandler

handler = GraphQLHandler(
    er_diagram: ErDiagram,
    resolver_class: Type[Resolver] = Resolver
)
```

### 执行查询

```python
result = await handler.execute(
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    operation_name: Optional[str] = None
) -> Dict[str, Any]
```

**返回值**:
```python
{
    'data': {...},  # 响应数据或 None
    'errors': [...]  # 错误列表或 None
}
```

## 框架集成

### 1. FastAPI

```python
from fastapi import FastAPI, APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from pydantic_resolve import base_entity, config_global_resolver
from pydantic_resolve.graphql import GraphQLHandler, SchemaBuilder

# 初始化
BaseEntity = base_entity()
config_global_resolver(BaseEntity.get_diagram())

app = FastAPI()

# 创建 handler 和 schema builder
handler = GraphQLHandler(BaseEntity.get_diagram())
schema_builder = SchemaBuilder(BaseEntity.get_diagram())

# 定义请求模型
class GraphQLRequest(BaseModel):
    query: str
    variables: Optional[Dict[str, Any]] = None
    operation_name: Optional[str] = None

# 创建路由
router = APIRouter()

@router.post("/graphql")
async def graphql_endpoint(req: GraphQLRequest):
    """GraphQL 查询端点"""
    result = await handler.execute(
        query=req.query,
        variables=req.variables,
        operation_name=req.operation_name
    )
    return result

@router.get("/schema", response_class=None)
async def graphql_schema():
    """GraphQL Schema 端点（SDL 格式）"""
    schema_sdl = schema_builder.build_schema()
    return PlainTextResponse(
        content=schema_sdl,
        media_type="text/plain; charset=utf-8"
    )

app.include_router(router)
```

### 2. Starlette

```python
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.requests import Request
from pydantic_resolve import base_entity, config_global_resolver
from pydantic_resolve.graphql import GraphQLHandler, SchemaBuilder

# 初始化
BaseEntity = base_entity()
config_global_resolver(BaseEntity.get_diagram())

handler = GraphQLHandler(BaseEntity.get_diagram())
schema_builder = SchemaBuilder(BaseEntity.get_diagram())

async def graphql_endpoint(request: Request):
    """GraphQL 查询端点"""
    data = await request.json()
    result = await handler.execute(
        query=data.get('query'),
        variables=data.get('variables'),
        operation_name=data.get('operation_name')
    )
    return JSONResponse(result)

async def schema_endpoint(request):
    """GraphQL Schema 端点"""
    schema_sdl = schema_builder.build_schema()
    return PlainTextResponse(schema_sdl)

routes = [
    Route('/graphql', graphql_endpoint, methods=['POST']),
    Route('/schema', schema_endpoint, methods=['GET']),
]

app = Starlette(routes=routes)
```

### 3. Flask

```python
from flask import Flask, request, jsonify, Response
from pydantic_resolve import base_entity, config_global_resolver
from pydantic_resolve.graphql import GraphQLHandler, SchemaBuilder

# 初始化
BaseEntity = base_entity()
config_global_resolver(BaseEntity.get_diagram())

app = Flask(__name__)
handler = GraphQLHandler(BaseEntity.get_diagram())
schema_builder = SchemaBuilder(BaseEntity.get_diagram())

@app.route('/graphql', methods=['POST'])
def graphql_endpoint():
    """GraphQL 查询端点"""
    data = request.get_json()
    result = await handler.execute(
        query=data.get('query'),
        variables=data.get('variables'),
        operation_name=data.get('operation_name')
    )
    return jsonify(result)

@app.route('/schema', methods=['GET'])
def schema_endpoint():
    """GraphQL Schema 端点"""
    schema_sdl = schema_builder.build_schema()
    return Response(schema_sdl, mimetype='text/plain')
```

### 4. Django

```python
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from pydantic_resolve import base_entity, config_global_resolver
from pydantic_resolve.graphql import GraphQLHandler, SchemaBuilder

# 初始化
BaseEntity = base_entity()
config_global_resolver(BaseEntity.get_diagram())

handler = GraphQLHandler(BaseEntity.get_diagram())
schema_builder = SchemaBuilder(BaseEntity.get_diagram())

@csrf_exempt
@require_http_methods(["POST"])
def graphql_endpoint(request):
    """GraphQL 查询端点"""
    if request.method == 'POST':
        data = json.loads(request.body)
        result = await handler.execute(
            query=data.get('query'),
            variables=data.get('variables'),
            operation_name=data.get('operation_name')
        )
        return JsonResponse(result)
    return JsonResponse({'error': 'Only POST allowed'}, status=405)

def schema_endpoint(request):
    """GraphQL Schema 端点"""
    schema_sdl = schema_builder.build_schema()
    return HttpResponse(schema_sdl, content_type='text/plain')
```

### 5. Tornado

```python
import tornado.web
import tornado.ioloop
from pydantic_resolve import base_entity, config_global_resolver
from pydantic_resolve.graphql import GraphQLHandler, SchemaBuilder

# 初始化
BaseEntity = base_entity()
config_global_resolver(BaseEntity.get_diagram())

handler = GraphQLHandler(BaseEntity.get_diagram())
schema_builder = SchemaBuilder(BaseEntity.get_diagram())

class GraphQLEndpoint(tornado.web.RequestHandler):
    async def post(self):
        """GraphQL 查询端点"""
        data = tornado.escape.json_decode(self.request.body)
        result = await handler.execute(
            query=data.get('query'),
            variables=data.get('variables'),
            operation_name=data.get('operation_name')
        )
        self.write(result)

class SchemaEndpoint(tornado.web.RequestHandler):
    def get(self):
        """GraphQL Schema 端点"""
        schema_sdl = schema_builder.build_schema()
        self.set_header('Content-Type', 'text/plain')
        self.write(schema_sdl)

def make_app():
    return tornado.web.Application([
        (r'/graphql', GraphQLEndpoint),
        (r'/schema', SchemaEndpoint),
    ])

if __name__ == '__main__':
    app = make_app()
    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()
```

## 高级用法

### 自定义响应格式

```python
from fastapi.responses import JSONResponse

@router.post("/graphql")
async def graphql_endpoint(req: GraphQLRequest):
    result = await handler.execute(
        query=req.query,
        variables=req.variables,
        operation_name=req.operation_name
    )

    # 添加自定义 headers
    return JSONResponse(
        content=result,
        headers={'X-Custom-Header': 'value'}
    )
```

### 错误处理

```python
@router.post("/graphql")
async def graphql_endpoint(req: GraphQLRequest):
    try:
        result = await handler.execute(
            query=req.query,
            variables=req.variables,
            operation_name=req.operation_name
        )
        return result
    except Exception as e:
        return {
            'data': None,
            'errors': [{'message': str(e)}]
        }
```

### 身份认证

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

@router.post("/graphql")
async def graphql_endpoint(
    req: GraphQLRequest,
    auth: str = Depends(security)
):
    # 验证 token
    if not is_valid_token(auth.credentials):
        raise HTTPException(status_code=401)

    result = await handler.execute(
        query=req.query,
        variables=req.variables,
        operation_name=req.operation_name
    )
    return result
```

### 请求上下文

```python
from pydantic_resolve import Resolver

async def graphql_endpoint(req: GraphQLRequest):
    # 将 context 传递给 resolver
    resolver = Resolver(context={'user_id': get_user_id(req)})

    handler = GraphQLHandler(
        er_diagram=BaseEntity.get_diagram(),
        resolver_class=lambda: resolver
    )

    result = await handler.execute(
        query=req.query,
        variables=req.variables,
        operation_name=req.operation_name
    )
    return result
```

## 相关资源

- [GraphQL Demo](https://github.com/allmonday/pydantic-resolve/tree/main/demo/graphql)
- [英文文档](./graphql-integration.md)
- [API 参考](https://allmonday.github.io/pydantic-resolve/api/)
