# GraphQL Framework Integration Guide

## Overview

`pydantic-resolve` provides `GraphQLHandler` as a framework-agnostic core for executing GraphQL queries. This guide shows how to integrate it with various web frameworks.

## Defining Entities and Queries/Mutations

pydantic-resolve supports two configuration methods for defining entities and their GraphQL operations.

### Method 1: BaseEntity with Decorators

Define entities that inherit from `BaseEntity`, using decorators for queries and mutations:

```python
from pydantic import BaseModel
from typing import List, Optional
from pydantic_resolve import base_entity, query, mutation, Relationship

BaseEntity = base_entity()

class UserEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(field='id', target_kls=list['PostEntity'],
                     loader=user_posts_loader, field_name='myposts')
    ]
    id: int
    name: str
    email: str

    @query(name='users')
    async def get_all(cls, limit: int = 10) -> List['UserEntity']:
        return await fetch_users(limit)

    @mutation(name='createUser')
    async def create(cls, name: str, email: str) -> 'UserEntity':
        return await create_user(name, email)

# Use BaseEntity.get_diagram() to get ErDiagram
handler = GraphQLHandler(BaseEntity.get_diagram())
```

### Method 2: ErDiagram with QueryConfig/MutationConfig

Define plain Pydantic models and configure them externally:

```python
from pydantic import BaseModel
from typing import List, Optional
from pydantic_resolve import Entity, ErDiagram, QueryConfig, MutationConfig, Relationship

class UserEntity(BaseModel):  # Only BaseModel, no BaseEntity
    id: int
    name: str
    email: str

# Standalone query function (no cls parameter needed)
async def get_all_users(limit: int = 10) -> List[UserEntity]:
    return await fetch_users(limit)

# Create ErDiagram with configuration
diagram = ErDiagram(configs=[
    Entity(
        kls=UserEntity,
        relationships=[
            Relationship(field='id', target_kls=list[PostEntity],
                         loader=user_posts_loader, field_name='myposts')
        ],
        queries=[
            QueryConfig(method=get_all_users, name='users', description='Get all users'),
        ],
        mutations=[
            MutationConfig(method=create_user, name='createUser', description='Create user'),
        ]
    ),
])

handler = GraphQLHandler(diagram)
```

### Comparison

| Feature | BaseEntity + Decorators | ErDiagram + Config |
|---------|------------------------|-------------------|
| Class inheritance | `BaseModel, BaseEntity` | `BaseModel` only |
| Query/Mutation location | Inside class | External functions |
| cls parameter | Required in methods | Not needed |
| Configuration style | Decorators | Explicit config objects |
| Best for | Self-contained entities | Separating concerns |

## Key Concepts

### field_name

Defines the GraphQL field name for nested queries:

```python
Relationship(
    field='author_id',           # FK field in entity
    target_kls=UserEntity,       # Target entity
    loader=user_loader,          # DataLoader function
    field_name='author'          # GraphQL field name
)
```

This allows queries like:
```graphql
{
  posts {
    title
    author { name }  # Uses field_name
  }
}
```

**Note:** `field_name` must not conflict with existing scalar fields in the entity.

### @query Decorator

Marks a class method as a GraphQL root query:

```python
@query(name='users', description='Get all users')
async def get_all(cls, limit: int = 10) -> List['UserEntity']:
    return await fetch_users(limit)
```

- Method is automatically converted to classmethod
- `name`: GraphQL query name (defaults to camelCase of method name)
- `description`: GraphQL schema description

### @mutation Decorator

Marks a class method as a GraphQL mutation:

```python
@mutation(name='createUser', description='Create a new user')
async def create_user(cls, name: str, email: str) -> 'UserEntity':
    return await create_user_in_db(name, email)
```

- Return type determines GraphQL output type
- `Optional[T]` -> nullable, `T` -> non-null
- `list[T]` -> `[T!]!` (non-null list of non-null items)

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
    operationName: Optional[str] = None

# Create router
router = APIRouter()

@router.post("/graphql")
async def graphql_endpoint(req: GraphQLRequest):
    """GraphQL query endpoint"""
    result = await handler.execute(
        query=req.query,
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
    )
    return result
```

## See Also

- [GraphQL Demo](https://github.com/allmonday/pydantic-resolve/tree/main/demo/graphql)
- [Chinese Documentation](./graphql.zh.md)
- [API Reference](https://allmonday.github.io/pydantic-resolve/api/)
