# UseCase MCP API

[中文版](./api_use_case_mcp.zh.md)

## create_use_case_mcp_server

```python
from pydantic_resolve.use_case import create_use_case_mcp_server

mcp = create_use_case_mcp_server(
    apps: list[UseCaseAppConfig],
    name: str = "Pydantic-Resolve UseCase API",
) -> "FastMCP"
```

Creates an MCP server that exposes `UseCaseService` methods to AI agents via progressive disclosure.

| Parameter | Type | Description |
|-----------|------|-------------|
| `apps` | `list[UseCaseAppConfig]` | Application configurations |
| `name` | `str` | MCP server name (default: `"Pydantic-Resolve UseCase API"`) |

Returns a configured `FastMCP` server instance.

```python
mcp = create_use_case_mcp_server(
    apps=[UseCaseAppConfig(name="project", services=[TaskService])]
)
mcp.run(transport="streamable-http", port=8080)
```

## UseCaseAppConfig

```python
from pydantic_resolve.use_case import UseCaseAppConfig

UseCaseAppConfig(
    name: str,
    services: list[type[UseCaseService]],
    description: str | None = None,
    enable_mutation: bool = True,
    context_extractor: Callable | None = None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Application name (required) |
| `services` | `list[type[UseCaseService]]` | List of UseCaseService subclasses (required) |
| `description` | `str \| None` | Application description for AI agents |
| `enable_mutation` | `bool` | Whether mutation methods are visible in MCP (default: `True`) |
| `context_extractor` | `Callable \| None` | Callback to extract request-scoped context |

### context_extractor

Optional callback that extracts request-scoped context (e.g. user identity from Authorization header) from the MCP HTTP request. The extracted dict is merged into method kwargs for parameters annotated with `FromContext`.

Signature: `(Context) -> dict | Awaitable[dict]`, supports both sync and async.

```python
from fastmcp.server.context import Context
from fastmcp.server.dependencies import get_http_headers

def extract_user_context(ctx: Context) -> dict:
    headers = get_http_headers(include={"authorization"})
    auth = headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        return {"user_id": int(token)}
    return {}

apps = [
    UseCaseAppConfig(
        name="project",
        services=[TaskService],
        context_extractor=extract_user_context,
    ),
]
```

Data flow:

```
HTTP Request (Authorization: Bearer <token>)
  → FastMCP Context
    → context_extractor(ctx) → {"user_id": 1}
      → call_use_case merges context into kwargs
        → TaskService.get_my_tasks(user_id=1)
```

**Important:** `get_http_headers()` excludes `authorization`, `content-type`, and other sensitive headers by default. You must pass `include={"authorization"}` to receive the Authorization header. When MCP runs via stdio transport (no HTTP request), `get_http_headers()` returns an empty dict.

## UseCaseService

```python
from pydantic_resolve.use_case import UseCaseService
from pydantic_resolve import query, mutation

class MyService(UseCaseService):
    """Service description (used by AI agents)."""

    @query
    async def my_method(cls, param1: int) -> MyDTO:
        """Method description (used by AI agents)."""
        ...
```

Base class for business service definitions. The `BusinessMeta` metaclass automatically discovers methods decorated with `@query` or `@mutation` and stores them for introspection.

**Conventions:**

- Methods must be decorated with `@query` or `@mutation` (from `pydantic_resolve`)
- Methods must be `async`
- Private methods (prefixed with `_`) and `get_tag_name` are excluded from discovery
- Docstrings on the class and methods become descriptions visible to AI agents
- Return type annotations are used for SDL type generation

### get_tag_name

```python
@classmethod
def get_tag_name(cls) -> str
```

Returns the class name by default. Override to customize the OpenAPI tag name when using with FastAPI:

```python
class TaskService(UseCaseService):
    @classmethod
    def get_tag_name(cls):
        return "Tasks"

# Usage in FastAPI
@app.get("/tasks", tags=[TaskService.get_tag_name()])
```

## FromContext

```python
from typing import Annotated
from pydantic_resolve.use_case import FromContext

user_id: Annotated[int, FromContext()]
```

Marker annotation for method parameters that should receive values from `context_extractor` rather than from the MCP tool's `params` JSON. This keeps the method signature identical for both FastAPI (parameter passed directly) and MCP (injected from context).

```python
class TaskService(UseCaseService):
    @query
    async def get_my_tasks(
        cls,
        user_id: Annotated[int, FromContext()],
    ) -> list[TaskSummary]:
        ...
```

- If the context key is present, it is injected into the method call
- If the context key is missing and the parameter has no default, an error is returned
- If the context key is missing and the parameter has a default, the default is used

## Progressive Disclosure Tools

The MCP server registers these tools automatically:

| Tool | Layer | Description |
|------|-------|-------------|
| `list_apps` | 0 | Discover available applications |
| `list_services` | 1 | List services in an app |
| `describe_service` | 2 | Get method signatures, parameter schemas, DTO type definitions, and selection hints |
| `call_use_case` | 3 | Execute a specific method |

The `describe_service` response now includes `selection_supported` and `selection_example` on each method, plus a top-level `selection_usage` block. Agents can use these fields to decide whether `call_use_case(selection=...)` is appropriate and how to format the projection.

### call_use_case

```python
call_use_case(
    app_name: str,
    service_name: str,
    method_name: str,
    params: str = "{}",
    selection: str | None = None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `app_name` | `str` | Application name (from `list_apps`) |
| `service_name` | `str` | Service name (from `list_services`) |
| `method_name` | `str` | Method name (from `describe_service`) |
| `params` | `str` | JSON string with method parameters (default: `"{}"`) |
| `selection` | `str \| None` | Optional rootless GraphQL-like field projection for Pydantic return values |

The `params` string is parsed as JSON and passed as keyword arguments to the method. Parameters annotated with `FromContext` are injected from the context_extractor result, not from `params`.

Use `selection` to reduce large Pydantic DTO responses before they are returned to the MCP client:

```python
call_use_case(
    app_name="project",
    service_name="TaskService",
    method_name="get_task",
    params='{"task_id": 1}',
    selection="{ id title owner { name } }",
)
```

The selection is applied after the use case method executes and before the existing response serialization layer. It only supports methods whose return annotation is a Pydantic model, `list[PydanticModel]`, or optional variants. Prefer the `types`, `selection_supported`, `selection_example`, and `selection_usage` values returned by `describe_service` when choosing fields and formatting the projection. Fields must exist on the return DTO, nested Pydantic DTO fields require sub-selections, scalar/dict/`Any` fields cannot have sub-selections, and GraphQL arguments are not supported.
