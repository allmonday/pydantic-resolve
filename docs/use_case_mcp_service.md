# UseCase MCP Service

[中文版](./use_case_mcp_service.zh.md)

This page solves one problem: you have business service methods powering FastAPI routes, and you want to expose the same logic to AI agents — without duplicating code.

## Goal

You have this:

```python
class TaskService(UseCaseService):
    @query
    async def list_tasks(cls) -> list[TaskSummary]:
        ...

    @query
    async def get_task(cls, task_id: int) -> TaskSummary | None:
        ...
```

You want AI agents to discover and call these methods through a standard MCP protocol:

```
Agent → "What services are available?"
      → list_apps() → ["project"]

Agent → "What can TaskService do?"
      → describe_service("project", "TaskService")
      → [list_tasks(), get_task(task_id)]

Agent → "Show me task 1"
      → call_use_case("project", "TaskService", "get_task", {"task_id": 1})
      → {id: 1, title: "Design docs", owner_name: "Ada"}
```

The same `TaskService` classmethods power both FastAPI routes and MCP tool calls. Business logic lives in one place.

## Install

```bash
pip install pydantic-resolve[mcp]
```

## Step 1: Define Services

Create service classes with `@query` and `@mutation` decorators. Docstrings become descriptions visible to AI agents:

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


class UserService(UseCaseService):  # (1)
    """User management service."""

    @query  # (2)
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

1.  `UseCaseService` uses a metaclass to discover methods decorated with `@query` or `@mutation`.
2.  The docstring becomes the tool description that AI agents see.

## Step 2: Create MCP Server

```python
from pydantic_resolve.use_case import UseCaseAppConfig, create_use_case_mcp_server

mcp = create_use_case_mcp_server(  # (1)
    apps=[
        UseCaseAppConfig(
            name="project",  # (2)
            services=[UserService, TaskService],  # (3)
            description="Project management with users and tasks",
        ),
    ],
    name="Project UseCase API",
)

mcp.run(transport="streamable-http", port=8080)  # (4)
```

1.  `create_use_case_mcp_server` scans services and generates MCP tools.
2.  `name` is the app identifier agents use to target a specific group of services.
3.  Pass service classes directly — no need to instantiate them.
4.  Starts an HTTP server that MCP clients connect to.

## How the Discovery Works

The MCP server exposes four tools that guide AI agents step by step:

```mermaid
sequenceDiagram
    participant A as AI Agent
    participant M as MCP Server
    participant S as TaskService

    A->>M: list_apps()
    M-->>A: ["project"]

    A->>M: list_services("project")
    M-->>A: ["UserService", "TaskService"]

    A->>M: describe_service("project", "TaskService")
    M-->>A: methods, schemas, selection hints

    A->>M: call_use_case("project", "TaskService", "get_task", {"task_id": 1})
    M->>S: TaskService.get_task(task_id=1)
    S-->>M: TaskSummary(...)
    M-->>A: {id: 1, title: "Design docs", ...}
```

1.  `list_apps` — discover available applications.
2.  `list_services` — list services within an app.
3.  `describe_service` — show method signatures, parameter schemas, and DTO type definitions.
4.  `call_use_case` — execute a method and return the result.

!!! tip "Selection support"

    For methods returning Pydantic DTOs, `call_use_case` accepts an optional `selection` parameter — a rootless GraphQL-like projection string. It filters the response fields without changing method parameters, data loading, or business execution.

    `describe_service` includes `selection_supported` and `selection_example` on each method so agents know when and how to use it.

## FromContext: Inject Request Context

When a method needs user identity or other request-scoped data, mark parameters with `FromContext`:

```python
from typing import Annotated
from pydantic_resolve.use_case import FromContext


class TaskService(UseCaseService):
    @query
    async def get_my_tasks(
        cls,
        user_id: Annotated[int, FromContext()],  # (1)
    ) -> list[TaskSummary]:
        """Get tasks owned by the authenticated user."""
        ...
```

1.  `FromContext()` tells the MCP server to inject this parameter from the request context, not from the agent's `params` JSON.

Then configure a `context_extractor` on the app:

```python
from fastmcp.server.context import Context
from fastmcp.server.dependencies import get_http_headers


def extract_user_context(ctx: Context) -> dict:
    headers = get_http_headers(include={"authorization"})  # (1)
    auth = headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        return {"user_id": int(token)}
    return {}


mcp = create_use_case_mcp_server(
    apps=[
        UseCaseAppConfig(
            name="project",
            services=[TaskService],
            context_extractor=extract_user_context,  # (2)
        ),
    ],
)
```

1.  `get_http_headers()` excludes `authorization` by default. Pass `include={"authorization"}` to receive it.
2.  The extractor runs on every request. Its return dict is merged into method kwargs.

Data flow:

```mermaid
flowchart LR
    A["HTTP Request<br/>Bearer token"] --> B["FastMCP Context"]
    B --> C["context_extractor"]
    C --> D["call_use_case"]
    D --> E["TaskService.get_my_tasks<br/>user_id=1"]
```

The method signature stays identical for FastAPI usage — just pass `user_id` directly:

```python
from fastapi import Depends

@app.get("/my-tasks")
async def my_tasks(user_id: int = Depends(get_current_user_id)):
    return await TaskService.get_my_tasks(user_id=user_id)
```

## Share Services with FastAPI

The same classmethods power both HTTP API and MCP:

```python
from pydantic_resolve.utils.types import get_return_annotation


@app.get("/api/tasks", tags=[TaskService.get_tag_name()])
async def get_tasks():
    return await TaskService.list_tasks()


@app.get(
    "/api/tasks/{task_id}",
    response_model=get_return_annotation(TaskService.get_task),  # (1)
    tags=[TaskService.get_tag_name()],
)
async def get_task(task_id: int):
    result = await TaskService.get_task(task_id=task_id)
    if result is None:
        raise HTTPException(status_code=404)
    return result
```

1.  `get_return_annotation` extracts the return type from the classmethod, so you can use it as FastAPI's `response_model` without repeating the type.

## Control Mutation Visibility

To hide mutation methods from AI agents, set `enable_mutation=False`:

```python
from pydantic_resolve import query, mutation


class TaskService(UseCaseService):
    @query
    async def list_tasks(cls) -> list[TaskSummary]:
        ...

    @mutation
    async def create_task(cls, title: str) -> TaskSummary:
        ...


mcp = create_use_case_mcp_server(
    apps=[
        UseCaseAppConfig(
            name="readonly-project",
            services=[TaskService],
            enable_mutation=False,  # (1)
        ),
    ],
)
```

1.  When `enable_mutation=False`: `list_services` excludes mutation methods from the count, `describe_service` omits them, and `call_use_case` returns an error if one is called.

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

## GraphQL MCP vs UseCase MCP

| | GraphQL MCP | UseCase MCP |
|---|---|---|
| Input | ER Diagram | `UseCaseService` classes |
| Query | GraphQL syntax | Method signatures |
| Best for | Flexible ad-hoc queries | Fixed business operations |
| Setup | `create_mcp_server` + ERD | `create_use_case_mcp_server` + services |

If you already have `UseCaseService` classes powering your FastAPI endpoints, UseCase MCP is the natural choice — zero duplication.

## Next

- [UseCase MCP API](./api_use_case_mcp.md) — detailed API signatures.
- [MCP Service](./mcp_service.md) — the GraphQL-based MCP approach.
