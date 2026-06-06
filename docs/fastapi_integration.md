# FastAPI Integration

[中文版](./fastapi_integration.zh.md)

pydantic-resolve works naturally with FastAPI since both use Pydantic models. This page covers common integration patterns.

## Goal

You want a FastAPI endpoint that returns resolved data — with relationships loaded and derived fields computed — in a single request:

```json
[
    {"id": 10, "title": "Design docs", "owner_id": 7, "owner": {"id": 7, "name": "Ada"}},
    {"id": 11, "title": "Refine examples", "owner_id": 8, "owner": {"id": 8, "name": "Bob"}}
]
```

No N+1 queries. No manual join logic in the route handler.

## Step 1: Resolve Inside the Route Handler

```python
from fastapi import FastAPI
from pydantic import BaseModel
from pydantic_resolve import Loader, Resolver

app = FastAPI()


class UserView(BaseModel):
    id: int
    name: str


class TaskView(BaseModel):
    id: int
    title: str
    owner_id: int
    owner: Optional[UserView] = None

    def resolve_owner(self, loader=Loader(user_loader)):  # (1)
        return loader.load(self.owner_id)


@app.get("/tasks", response_model=list[TaskView])
async def get_tasks():
    tasks = await fetch_tasks_from_db()
    task_views = [TaskView.model_validate(t) for t in tasks]
    return await Resolver().resolve(task_views)  # (2)
```

1.  `resolve_owner` declares the missing field — same as in Quick Start.
2.  `Resolver().resolve()` traverses the tree and batch-loads all relationships. `response_model` handles serialization.

## Step 2: Pass Request Context

Use `Resolver(context=...)` to pass request-scoped data into `post_*` methods:

```python
from fastapi import Request


@app.get("/tasks")
async def get_tasks(request: Request):
    user_id = request.state.user_id
    tasks = await fetch_tasks()
    task_views = [TaskView.model_validate(t) for t in tasks]
    return await Resolver(context={
        'user_id': user_id,
        'permissions': ['read', 'write'],
    }).resolve(task_views)


class TaskView(BaseModel):
    owner: Optional[UserView] = None
    can_edit: bool = False

    def resolve_owner(self, loader=Loader(user_loader)):
        return loader.load(self.owner_id)

    def post_can_edit(self, context):  # (1)
        return 'write' in context.get('permissions', [])
```

1.  `context` is the dict passed to `Resolver()`. Use it for permissions, locale, or any request-scoped data.

## Step 3: Use FastAPI Dependencies with Loader Params

Combine FastAPI dependency injection with loader parameters:

```python
from fastapi import Depends, Query


async def get_status_filter(status: str = Query('active')) -> str:
    return status


@app.get("/companies")
async def get_companies(status: str = Depends(get_status_filter)):
    companies = await fetch_companies()
    return await Resolver(
        loader_params={OfficeLoader: {'status': status}}  # (1)
    ).resolve(companies)
```

1.  `loader_params` passes the filter to the loader's batch function. Each loader receives only the params declared for it.

## Sharing Resolver Configuration

When multiple endpoints share the same configuration, create a factory:

```python
def make_resolver(request: Request) -> Resolver:
    return Resolver(
        context={'user_id': request.state.user_id},
        loader_params={
            OfficeLoader: {'status': 'active'},
        },
    )


@app.get("/tasks")
async def get_tasks(request: Request):
    resolver = make_resolver(request)
    tasks = await fetch_tasks()
    return await resolver.resolve([TaskView.model_validate(t) for t in tasks])


@app.get("/sprints")
async def get_sprints(request: Request):
    resolver = make_resolver(request)
    sprints = await fetch_sprints()
    return await resolver.resolve([SprintView.model_validate(s) for s in sprints])
```

## Error Handling

Wrap resolver calls in try/except for clean error responses:

```python
from pydantic_resolve import LoaderFieldNotProvidedError


@app.get("/tasks")
async def get_tasks():
    try:
        tasks = await fetch_tasks()
        return await Resolver(
            loader_params={OfficeLoader: {'status': 'active'}}
        ).resolve([TaskView.model_validate(t) for t in tasks])
    except LoaderFieldNotProvidedError as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## OpenAPI Schema Generation

FastAPI automatically generates OpenAPI schemas from your Pydantic models. Fields that start as `None` with `Optional` types appear correctly:

```python
class TaskView(BaseModel):
    id: int
    title: str
    owner_id: int
    owner: Optional[UserView] = None  # appears as nullable in OpenAPI

    def resolve_owner(self, loader=Loader(user_loader)):
        return loader.load(self.owner_id)
```

The `owner` field shows up as `{"oneOf": [{"type": "null"}, {"$ref": "UserView"}]}`.

If you want to exclude resolved fields from the input schema while keeping them in the output, use separate request/response models:

```python
class TaskCreate(BaseModel):
    """Input model — no resolved fields"""
    title: str
    owner_id: int


class TaskResponse(BaseModel):
    """Output model — includes resolved fields"""
    id: int
    title: str
    owner_id: int
    owner: Optional[UserView] = None

    def resolve_owner(self, loader=Loader(user_loader)):
        return loader.load(self.owner_id)


@app.post("/tasks", response_model=TaskResponse)
async def create_task(data: TaskCreate):
    task = await create_task_in_db(data)
    task_view = TaskResponse.model_validate(task)
    return await Resolver().resolve(task_view)
```

## Performance

1.  **One `Resolver()` per request.** The resolver creates fresh DataLoader instances each time, so batches are scoped correctly.

2.  **Resolve the full list at once.** Don't resolve inside loops:

    ```python
    # BAD: N resolver calls
    results = []
    for task in tasks:
        result = await Resolver().resolve(TaskView.model_validate(task))
        results.append(result)

    # GOOD: one resolver call
    task_views = [TaskView.model_validate(t) for t in tasks]
    results = await Resolver().resolve(task_views)
    ```

3.  **Use `response_model` for serialization.** Let FastAPI handle the JSON conversion — don't call `model_dump()` manually.

4.  **Debug mode.** Enable `Resolver(debug=True)` during development to see timing per node.

## Next

Continue to [GraphQL Guide](./graphql_guide.md) to learn how to generate GraphQL from ERD, or [MCP Service](./mcp_service.md) to expose APIs to AI agents.
