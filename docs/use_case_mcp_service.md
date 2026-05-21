# UseCase MCP Service

[中文版](./use_case_mcp_service.zh.md)

UseCase MCP lets you expose business service methods directly to AI agents, without going through GraphQL. The same `UseCaseService` classes serve both FastAPI HTTP routes and MCP tool calls — business logic lives in one place.

## When to Use This vs GraphQL MCP

| | GraphQL MCP | UseCase MCP |
|---|---|---|
| Input | ER Diagram | `UseCaseService` classes |
| Query | GraphQL syntax | Method signatures |
| Best for | Flexible ad-hoc queries | Fixed business operations |
| Setup | `create_mcp_server` + ERD | `create_use_case_mcp_server` + services |

If you already have `UseCaseService` classes powering your FastAPI endpoints, UseCase MCP is the natural choice — zero duplication.

## Install

```bash
pip install pydantic-resolve[mcp]
```

## Quick Start

### 1. Define services

```python
from pydantic import BaseModel
from pydantic_resolve import query
from pydantic_resolve.use_case import UseCaseService


class UserSummary(BaseModel):
    id: int
    name: str


class TaskSummary(BaseModel):
    id: int
    title: str
    owner_name: str


class UserService(UseCaseService):
    """User management service."""

    @query
    async def list_users(cls) -> list[UserSummary]:
        """Get all users."""
        ...


class TaskService(UseCaseService):
    """Task management service."""

    @query
    async def list_tasks(cls) -> list[TaskSummary]:
        """Get all tasks."""
        ...

    @query
    async def get_task(cls, task_id: int) -> TaskSummary | None:
        """Get a task by ID."""
        ...
```

`UseCaseService` uses a metaclass to automatically discover methods decorated with `@query` or `@mutation`. Docstrings become descriptions visible to AI agents.

### 2. Create MCP server

```python
from pydantic_resolve.use_case import UseCaseAppConfig, create_use_case_mcp_server

mcp = create_use_case_mcp_server(
    apps=[
        UseCaseAppConfig(
            name="project",
            services=[UserService, TaskService],
            description="Project management with users and tasks",
        ),
    ],
    name="Project UseCase API",
)

mcp.run(transport="streamable-http", port=8080)
```

## Progressive Disclosure

The MCP server exposes four tools that guide AI agents step by step:

```
Layer 0: list_apps         → "What applications are available?"
Layer 1: list_services     → "What services does this app have?"
Layer 2: describe_service  → "What methods and types does this service expose?"
Layer 3: call_use_case     → "Execute a specific method"
```

Example flow:

1. Agent calls `list_apps` → discovers `["project"]`
2. Agent calls `list_services(app_name="project")` → discovers `["UserService", "TaskService"]`
3. Agent calls `describe_service(app_name="project", service_name="TaskService")` → sees method signatures, parameter schemas, and DTO type definitions
4. Agent calls `call_use_case(app_name="project", service_name="TaskService", method_name="get_task", params='{"task_id": 1}', selection="{ id title owner { name } }")` → gets a compact result

`describe_service` returns SDL-style type definitions for all DTOs referenced by the service, and now also includes `selection_supported` / `selection_example` on each method plus a top-level `selection_usage` block. Agents can use these fields to decide whether a method is a good fit for `selection` and how to format the projection.
For methods returning Pydantic DTOs, `call_use_case` can also accept a rootless GraphQL-like `selection` string to return only selected fields. The selection is a response projection only: it does not change method parameters, data loading, pagination, or business execution.

## FromContext: Inject Request Context

When a method needs user identity or other request-scoped data, use `FromContext` to mark parameters that should be injected from the MCP context rather than from the tool's `params` JSON:

```python
from typing import Annotated
from pydantic_resolve import query
from pydantic_resolve.use_case import UseCaseService, FromContext

class TaskService(UseCaseService):
    @query
    async def get_my_tasks(
        cls,
        user_id: Annotated[int, FromContext()],
    ) -> list[TaskSummary]:
        """Get tasks owned by the authenticated user."""
        ...
```

Then configure a `context_extractor` on the app:

```python
from fastmcp.server.context import Context
from fastmcp.server.dependencies import get_http_headers

def extract_user_context(ctx: Context) -> dict:
    headers = get_http_headers(include={"authorization"})
    auth = headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        return {"user_id": int(token)}  # In production, decode JWT here
    return {}

mcp = create_use_case_mcp_server(
    apps=[
        UseCaseAppConfig(
            name="project",
            services=[TaskService],
            context_extractor=extract_user_context,
        ),
    ],
)
```

Data flow:

```
HTTP Request (Authorization: Bearer <token>)
  → FastMCP Context
    → context_extractor(ctx) → {"user_id": 1}
      → call_use_case merges context into kwargs
        → TaskService.get_my_tasks(user_id=1)
```

The method signature stays identical for FastAPI usage — just pass `user_id` directly:

```python
# FastAPI route
@app.get("/my-tasks")
async def my_tasks(user_id: int = Depends(get_current_user_id)):
    return await TaskService.get_my_tasks(user_id=user_id)
```

**Important:** `get_http_headers()` excludes `authorization` by default. You must pass `include={"authorization"}` to receive it.

## Share Services with FastAPI

The primary value of `UseCaseService` is that business logic lives in one place. The same classmethods power both HTTP API and MCP:

```python
from pydantic_resolve.utils.types import get_return_annotation

@app.get("/api/tasks", tags=[TaskService.get_tag_name()])
async def get_tasks():
    return await TaskService.list_tasks()

@app.get(
    "/api/tasks/{task_id}",
    response_model=get_return_annotation(TaskService.get_task),
    tags=[TaskService.get_tag_name()],
)
async def get_task(task_id: int):
    result = await TaskService.get_task(task_id=task_id)
    if result is None:
        raise HTTPException(status_code=404)
    return result
```

`get_return_annotation` extracts the return type from the classmethod, so you can use it as FastAPI's `response_model` without repeating the type.

## Control Mutation Visibility

By default, all methods (both `@query` and `@mutation`) are visible to AI agents. To hide mutation methods from a specific app, set `enable_mutation=False`:

```python
from pydantic_resolve import query, mutation

class TaskService(UseCaseService):
    @query
    async def list_tasks(cls) -> list[TaskSummary]:
        """Get all tasks."""
        ...

    @mutation
    async def create_task(cls, title: str) -> TaskSummary:
        """Create a new task."""
        ...

mcp = create_use_case_mcp_server(
    apps=[
        UseCaseAppConfig(
            name="readonly-project",
            services=[TaskService],
            enable_mutation=False,  # hide mutation methods
        ),
    ],
)
```

When `enable_mutation=False`:
- `list_services` excludes mutation methods from the count
- `describe_service` omits mutation methods from the response
- `call_use_case` returns an error if a mutation method is called

This is useful for providing read-only access to AI agents while keeping write operations restricted.

## Multi-App Support

Serve multiple independent application groups from one MCP server:

```python
mcp = create_use_case_mcp_server(
    apps=[
        UseCaseAppConfig(name="project", services=[SprintService, TaskService]),
        UseCaseAppConfig(name="admin", services=[UserService, RoleService]),
    ],
    name="My Platform",
)
```

Each app has its own services and optional `context_extractor`.

## Next

- [UseCase MCP API](./api_use_case_mcp.md) for detailed API signatures
- [MCP Service](./mcp_service.md) for the GraphQL-based MCP approach
