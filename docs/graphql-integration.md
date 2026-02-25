# GraphQL Framework Integration Guide

## Overview

`pydantic-resolve` provides `GraphQLHandler` as a framework-agnostic core for executing GraphQL queries. This guide shows how to integrate it with various web frameworks.

## GraphQLHandler API

### Constructor

```python
from pydantic_resolve.graphql import GraphQLHandler

handler = GraphQLHandler(
    er_diagram: ErDiagram,
    resolver_class: Type[Resolver] = Resolver
)
```

### Execute Query

```python
result = await handler.execute(
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    operation_name: Optional[str] = None
) -> Dict[str, Any]
```

**Returns**:
```python
{
    'data': {...},  # Response data or None
    'errors': [...]  # List of errors or None
}
```

## Framework Integrations

### 1. FastAPI

```python
from fastapi import FastAPI, APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from pydantic_resolve import base_entity, config_global_resolver
from pydantic_resolve.graphql import GraphQLHandler, SchemaBuilder

# Initialize
BaseEntity = base_entity()
config_global_resolver(BaseEntity.get_diagram())

app = FastAPI()

# Create handler and schema builder
handler = GraphQLHandler(BaseEntity.get_diagram())
schema_builder = SchemaBuilder(BaseEntity.get_diagram())

# Define request model
class GraphQLRequest(BaseModel):
    query: str
    variables: Optional[Dict[str, Any]] = None
    operation_name: Optional[str] = None

# Create router
router = APIRouter()

@router.post("/graphql")
async def graphql_endpoint(req: GraphQLRequest):
    """GraphQL query endpoint"""
    result = await handler.execute(
        query=req.query,
        variables=req.variables,
        operation_name=req.operation_name
    )
    return result

@router.get("/schema", response_class=None)
async def graphql_schema():
    """GraphQL Schema endpoint (SDL format)"""
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

# Initialize
BaseEntity = base_entity()
config_global_resolver(BaseEntity.get_diagram())

handler = GraphQLHandler(BaseEntity.get_diagram())
schema_builder = SchemaBuilder(BaseEntity.get_diagram())

async def graphql_endpoint(request: Request):
    """GraphQL query endpoint"""
    data = await request.json()
    result = await handler.execute(
        query=data.get('query'),
        variables=data.get('variables'),
        operation_name=data.get('operation_name')
    )
    return JSONResponse(result)

async def schema_endpoint(request):
    """GraphQL Schema endpoint"""
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

# Initialize
BaseEntity = base_entity()
config_global_resolver(BaseEntity.get_diagram())

app = Flask(__name__)
handler = GraphQLHandler(BaseEntity.get_diagram())
schema_builder = SchemaBuilder(BaseEntity.get_diagram())

@app.route('/graphql', methods=['POST'])
def graphql_endpoint():
    """GraphQL query endpoint"""
    data = request.get_json()
    result = await handler.execute(
        query=data.get('query'),
        variables=data.get('variables'),
        operation_name=data.get('operation_name')
    )
    return jsonify(result)

@app.route('/schema', methods=['GET'])
def schema_endpoint():
    """GraphQL Schema endpoint"""
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

# Initialize
BaseEntity = base_entity()
config_global_resolver(BaseEntity.get_diagram())

handler = GraphQLHandler(BaseEntity.get_diagram())
schema_builder = SchemaBuilder(BaseEntity.get_diagram())

@csrf_exempt
@require_http_methods(["POST"])
def graphql_endpoint(request):
    """GraphQL query endpoint"""
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
    """GraphQL Schema endpoint"""
    schema_sdl = schema_builder.build_schema()
    return HttpResponse(schema_sdl, content_type='text/plain')
```

### 5. Tornado

```python
import tornado.web
import tornado.ioloop
from pydantic_resolve import base_entity, config_global_resolver
from pydantic_resolve.graphql import GraphQLHandler, SchemaBuilder

# Initialize
BaseEntity = base_entity()
config_global_resolver(BaseEntity.get_diagram())

handler = GraphQLHandler(BaseEntity.get_diagram())
schema_builder = SchemaBuilder(BaseEntity.get_diagram())

class GraphQLEndpoint(tornado.web.RequestHandler):
    async def post(self):
        """GraphQL query endpoint"""
        data = tornado.escape.json_decode(self.request.body)
        result = await handler.execute(
            query=data.get('query'),
            variables=data.get('variables'),
            operation_name=data.get('operation_name')
        )
        self.write(result)

class SchemaEndpoint(tornado.web.RequestHandler):
    def get(self):
        """GraphQL Schema endpoint"""
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

## Advanced Usage

### Custom Response Formatting

```python
from fastapi.responses import JSONResponse

@router.post("/graphql")
async def graphql_endpoint(req: GraphQLRequest):
    result = await handler.execute(
        query=req.query,
        variables=req.variables,
        operation_name=req.operation_name
    )

    # Add custom headers
    return JSONResponse(
        content=result,
        headers={'X-Custom-Header': 'value'}
    )
```

### Error Handling

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

### Authentication

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

@router.post("/graphql")
async def graphql_endpoint(
    req: GraphQLRequest,
    auth: str = Depends(security)
):
    # Validate token
    if not is_valid_token(auth.credentials):
        raise HTTPException(status_code=401)

    result = await handler.execute(
        query=req.query,
        variables=req.variables,
        operation_name=req.operation_name
    )
    return result
```

### Request Context

```python
from pydantic_resolve import Resolver

async def graphql_endpoint(req: GraphQLRequest):
    # Pass context to resolver
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

## See Also

- [GraphQL Demo](https://github.com/allmonday/pydantic-resolve/tree/main/demo/graphql)
- [Chinese Documentation](./graphql-integration.zh.md)
- [API Reference](https://allmonday.github.io/pydantic-resolve/api/)
