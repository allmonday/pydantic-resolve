# FastAPI 集成

[English](./fastapi_integration.md)

pydantic-resolve 与 FastAPI 自然协作，因为两者都使用 Pydantic 模型。本页面介绍常见的集成模式。

## 基本模式

在路由处理程序中使用 `Resolver().resolve()`：

```python
from fastapi import FastAPI
from pydantic import BaseModel
from pydantic_resolve import Loader, Resolver, build_object

app = FastAPI()


class UserView(BaseModel):
    id: int
    name: str


class TaskView(BaseModel):
    id: int
    title: str
    owner_id: int
    owner: Optional[UserView] = None

    def resolve_owner(self, loader=Loader(user_loader)):
        return loader.load(self.owner_id)


@app.get("/tasks", response_model=list[TaskView])
async def get_tasks():
    tasks = await fetch_tasks_from_db()
    task_views = [TaskView.model_validate(t) for t in tasks]
    return await Resolver().resolve(task_views)
```

FastAPI 中的 `response_model` 参数处理序列化。resolver 处理数据组装。

## 传递请求上下文

使用 `Resolver(context=...)` 传递请求范围的数据：

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

    def post_can_edit(self, context):
        return 'write' in context.get('permissions', [])
```

## 来自依赖的 Loader 参数

结合 FastAPI 依赖注入与 loader 参数：

```python
from fastapi import Depends, Query


async def get_status_filter(status: str = Query('active')) -> str:
    return status


@app.get("/companies")
async def get_companies(status: str = Depends(get_status_filter)):
    companies = await fetch_companies()
    return await Resolver(
        loader_params={OfficeLoader: {'status': status}}
    ).resolve(companies)
```

## 共享 Resolver 配置

当多个端点共享相同配置时，创建一个工厂：

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

## 错误处理

将 resolver 调用包装在 try/except 中以获得清晰的错误响应：

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

## 性能考虑

1. **每个请求一个 `Resolver()`。** resolver 每次都创建新的 DataLoader 实例，因此批次范围正确。

2. **避免在循环内解析。** 一次性解析整个列表，而不是逐项解析：

    ```python
    # 错误：N 个 resolver 调用
    results = []
    for task in tasks:
        result = await Resolver().resolve(TaskView.model_validate(task))
        results.append(result)

    # 正确：一个 resolver 调用
    task_views = [TaskView.model_validate(t) for t in tasks]
    results = await Resolver().resolve(task_views)
    ```

3. **使用 `response_model` 进行序列化。** 让 FastAPI 处理 JSON 转换 — 不要手动调用 `model_dump()`。

4. **调试模式。** 在开发期间启用 `Resolver(debug=True)` 以查看每个节点的计时。

## OpenAPI Schema 生成

FastAPI 自动从你的 Pydantic 模型生成 OpenAPI schema。以 `None` 和 `Optional` 类型开头的字段会正确显示：

```python
class TaskView(BaseModel):
    id: int
    title: str
    owner_id: int
    owner: Optional[UserView] = None  # 在 OpenAPI 中显示为可空

    def resolve_owner(self, loader=Loader(user_loader)):
        return loader.load(self.owner_id)
```

`owner` 字段在 schema 中显示为 `{"owner": {"oneOf": [{"type": "null"}, {"$ref": "UserView"}]}}`。

如果你想从输入 schema 中排除已解析的字段，同时将它们保留在输出中，请使用单独的请求/响应模型：

```python
class TaskCreate(BaseModel):
    """输入模型 — 没有已解析的字段"""
    title: str
    owner_id: int


class TaskResponse(BaseModel):
    """输出模型 — 包含已解析的字段"""
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

## 下一步

继续阅读 [GraphQL 指南](./graphql_guide.zh.md) 了解如何从 ERD 生成 GraphQL，或 [MCP 服务](./mcp_service.zh.md) 向 AI 代理暴露 API。
