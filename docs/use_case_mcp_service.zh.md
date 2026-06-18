# UseCase MCP 服务

[English](./use_case_mcp_service.md)

UseCase MCP 可以将业务服务方法直接暴露给 AI agent。同一套 `UseCaseService` 类同时服务 FastAPI HTTP 路由和 MCP 工具调用——业务逻辑只维护一份。

## 与 GraphQL MCP 的选择

| | GraphQL MCP | UseCase MCP |
|---|---|---|
| 输入 | ER Diagram | `UseCaseService` 类 |
| 查询方式 | 完整 GraphQL | GraphQL compose（固定 3 层：Service → Method → DTO 字段） |
| 适用场景 | 灵活的即席查询 | 固定的业务操作 |
| 入口 | `create_mcp_server` + ERD | `create_use_case_graphql_mcp_server` + services |

如果你已经有 `UseCaseService` 类驱动 FastAPI 端点，UseCase MCP 是自然的选择——零重复。

## 安装

```bash
pip install pydantic-resolve[mcp]
```

## 快速开始

### 1. 定义服务

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
    """用户管理服务。"""

    @query
    async def list_users(cls) -> list[UserSummary]:
        """获取所有用户。"""
        ...


class TaskService(UseCaseService):
    """任务管理服务。"""

    @query
    async def list_tasks(cls) -> list[TaskSummary]:
        """获取所有任务。"""
        ...

    @query
    async def get_task(cls, task_id: int) -> TaskSummary | None:
        """根据 ID 获取任务。"""
        ...
```

`UseCaseService` 通过元类自动发现被 `@query` 或 `@mutation` 装饰的方法。类和方法的 docstring 会作为描述展示给 AI agent。

### 2. 创建 MCP 服务

```python
from pydantic_resolve.use_case import UseCaseAppConfig, create_use_case_graphql_mcp_server

mcp = create_use_case_graphql_mcp_server(
    apps=[
        UseCaseAppConfig(
            name="project",
            services=[UserService, TaskService],
            description="项目管理系统，包含用户和任务",
        ),
    ],
    name="项目 UseCase GraphQL API",
)

mcp.run(transport="streamable-http", port=8080)
```

## 渐进式发现

MCP 服务提供四个工具，构成一个发现漏斗：

```
Layer 1: list_apps              → "有哪些应用？"
Layer 2: describe_compose_schema → "这个应用有哪些 service 和 method？"
Layer 3: describe_compose_method → "这个方法的参数、返回类型、字段树是什么？"
Layer 4: compose_query           → "对 compose surface 执行 GraphQL 查询"
```

调用流程示例：

1. Agent 调用 `list_apps` → 发现 `["project"]`
2. Agent 调用 `describe_compose_schema(app_name="project")` → 看到 services 和 methods 的紧凑列表（名称 + 类型 + 描述）
3. Agent 调用 `describe_compose_method(app_name="project", service_name="TaskService", method_name="get_task")` → 看到参数、返回类型和 SDL（包含返回 DTO 及其所有嵌套 DTO）
4. Agent 调用 `compose_query(app_name="project", query="{ TaskService { get_task(task_id: 1) { title owner { name } } } }")` → 获得结构化结果

`describe_compose_method` 返回的 `sdl` 字段是字段名的唯一真相来源 —— 顶层和嵌套字段都在里面。

`compose_query` 拒绝 GraphQL introspection（`__schema`、`__type`、`__typename`），schema 发现走 Layer 2 + 3。查询固定为 3 层结构：`Query → Service → Method → DTO 字段选择`，每个 service 下的 method 可以并发执行（mutation 串行）。

## FromContext：注入请求上下文

当方法需要用户身份等请求级数据时，用 `FromContext` 标记应从 MCP 上下文注入的参数，而非从 GraphQL 查询传入：

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
        """获取当前用户的任务。"""
        ...
```

然后在应用配置中设置 `context_extractor`：

```python
from fastmcp.server.context import Context
from fastmcp.server.dependencies import get_http_headers

def extract_user_context(ctx: Context) -> dict:
    headers = get_http_headers(include={"authorization"})
    auth = headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        return {"user_id": int(token)}  # 生产环境中应解码 JWT
    return {}

mcp = create_use_case_graphql_mcp_server(
    apps=[
        UseCaseAppConfig(
            name="project",
            services=[TaskService],
            context_extractor=extract_user_context,
        ),
    ],
)
```

数据流：

```
HTTP 请求 (Authorization: Bearer <token>)
  → FastMCP Context
    → context_extractor(ctx) → {"user_id": 1}
      → 方法调用时将 context 合并到 kwargs
        → TaskService.get_my_tasks(user_id=1)
```

方法签名在 FastAPI 中保持不变——直接传入 `user_id`：

```python
# FastAPI 路由
@app.get("/my-tasks")
async def my_tasks(user_id: int = Depends(get_current_user_id)):
    return await TaskService.get_my_tasks(user_id=user_id)
```

**注意：** `get_http_headers()` 默认会过滤 `authorization` 头。必须传入 `include={"authorization"}` 才能获取。

## 与 FastAPI 共用服务

`UseCaseService` 的核心价值是业务逻辑只维护一份。同一套 classmethod 同时驱动 HTTP API 和 MCP：

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

`get_return_annotation` 从 classmethod 中提取返回类型，用作 FastAPI 的 `response_model`，无需重复声明类型。

## 控制 Mutation 可见性

默认情况下，所有方法（`@query` 和 `@mutation`）都对 AI agent 可见。要隐藏某个应用的 mutation 方法，设置 `enable_mutation=False`：

```python
from pydantic_resolve import query, mutation

class TaskService(UseCaseService):
    @query
    async def list_tasks(cls) -> list[TaskSummary]:
        """获取所有任务。"""
        ...

    @mutation
    async def create_task(cls, title: str) -> TaskSummary:
        """创建新任务。"""
        ...

mcp = create_use_case_graphql_mcp_server(
    apps=[
        UseCaseAppConfig(
            name="readonly-project",
            services=[TaskService],
            enable_mutation=False,  # 隐藏 mutation 方法
        ),
    ],
)
```

当 `enable_mutation=False` 时：
- `describe_compose_schema` 的方法列表不包含 mutation
- `describe_compose_method` 对 mutation 方法返回错误
- `compose_query` 拒绝执行 mutation

适用于需要向 AI agent 提供只读访问权限，同时限制写操作的场景。

## 多应用支持

一个 MCP 服务可以承载多个独立的应用组：

```python
mcp = create_use_case_graphql_mcp_server(
    apps=[
        UseCaseAppConfig(name="project", services=[SprintService, TaskService]),
        UseCaseAppConfig(name="admin", services=[UserService, RoleService]),
    ],
    name="我的平台",
)
```

每个应用有独立的服务列表和可选的 `context_extractor`。

## 跨 Service 组合查询

`compose_query` 工具接收单条 GraphQL 查询，可一次性扇出到多个 service 和 method：

```python
compose_query(
    app_name="project",
    query='''
    {
      SprintService {
        list_sprints { id name }
        get_sprint(sprint_id: 1) { name }
      }
      TaskService {
        get_task(task_id: 1) { title owner_id }
        list_tasks { title }
      }
    }
    ''',
)
```

**执行语义：**

- `@query` 方法并发执行。
- `@mutation` 方法按声明顺序串行执行。
- 单次调用内 query 和 mutation 之间的相对顺序不保证 —— 「先创建后读取」的语义请拆成两次调用。

## 接下来

- [UseCase MCP API](./api_use_case_mcp.zh.md) 查看详细的 API 签名
- [MCP 服务](./mcp_service.zh.md) 了解基于 ER 图的 GraphQL MCP 方案
