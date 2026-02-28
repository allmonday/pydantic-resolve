# Pydantic Resolve

> 一个领域层建模与用例组装工具

[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![PyPI Downloads](https://static.pepy.tech/badge/pydantic-resolve/month)](https://pepy.tech/projects/pydantic-resolve)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)

## 这是什么？

**pydantic-resolve** 是一个基于 Pydantic 的声明式数据组装工具，让你可以用简洁的方式构建复杂的数据结构，无需编写繁琐的数据获取和组装代码。

它解决了三个核心问题：

1. **告别 N+1 查询**：内置 DataLoader 自动批量加载关联数据，无需手动管理批量查询逻辑
2. **清晰的分层架构**：Entity-First 设计让业务概念独立于数据存储，数据库变更不再影响 API 契约
3. **优雅的数据组合**：通过 `resolve`、`post`、`Expose`、`Collect` 等声明式方法，轻松处理跨层的数据传递和聚合

## 安装

```bash
pip install pydantic-resolve
```

> 注意：pydantic-resolve v2+ 仅支持 Pydantic v2

**更多资源**：[完整文档](https://allmonday.github.io/pydantic-resolve/) | [示例项目](https://github.com/allmonday/composition-oriented-development-pattern) | [在线演示](https://www.fastapi-voyager.top/voyager/) | [API 参考](https://allmonday.github.io/pydantic-resolve/api/)

---

## 一、基础功能 - Resolve, Post 和 DataLoader

### 面临的问题

在日常开发中，我们经常需要组装来自多个数据源的复杂数据结构。比如一个任务管理系统，你需要返回团队列表，包含每个团队的 Sprint，每个 Sprint 包含 Story，每个 Story 包含 Task，而每个 Task 又需要包含负责人信息。传统的方式会让你陷入循环的泥潭：先查询主数据，然后收集关联 ID，批量查询关联数据，手动构建映射字典，最后循环组装结果。这个过程不仅代码量大、易出错，还容易产生经典的 N+1 查询问题——忘记批量加载就会导致性能灾难。

即使你小心翼翼地实现了批量加载，这些数据组装逻辑也会散落在项目的各个角落。每个需要关联数据的 API 端点都会有一段类似的代码，违反了 DRY 原则，也使得数据加载策略的优化变得困难。更糟糕的是，这种命令式的数据获取方式将"如何获取数据"的技术细节与"需要什么数据"的业务逻辑混杂在一起，增加了认知负担。

### pydantic-resolve 的声明式解决方案

pydantic-resolve 让你用声明式的方式描述数据依赖，框架会自动处理数据获取和组装的细节。你只需要定义"这个任务需要一个 owner"，框架会自动收集所有需要的 owner ID，批量查询，然后填充到对应的位置。这不仅消除了 N+1 查询的风险，也让代码更加清晰和可维护。

声明式数据组装的核心是两个方法：`resolve_` 和 `post_`。`resolve_` 方法用于声明如何获取关联数据，`post_` 方法用于在所有数据加载完成后进行后处理和计算。配合 DataLoader 的自动批量加载，你可以用简洁的代码实现复杂的数据组装逻辑。

```python
from pydantic import BaseModel
from typing import Optional, List
from pydantic_resolve import Resolver, Loader, build_list

# 定义批量数据加载器
async def user_batch_loader(user_ids: list[int]):
    async with get_db_session() as session:
        result = await session.execute(select(User).where(User.id.in_(user_ids)))
        users = result.scalars().all()
        return build_list(users, user_ids, lambda u: u.id)

# 定义响应模型
class UserResponse(BaseModel):
    id: int
    name: str
    email: str

class TaskResponse(BaseModel):
    id: int
    name: str
    owner_id: int

    # 声明：通过 owner_id 获取 owner
    owner: Optional[UserResponse] = None
    def resolve_owner(self, loader=Loader(user_batch_loader)):
        return loader.load(self.owner_id)

class SprintResponse(BaseModel):
    id: int
    name: str

    # 声明：通过 sprint_id 获取该 Sprint 的所有 tasks
    tasks: List[TaskResponse] = []
    def resolve_tasks(self, loader=Loader(sprint_to_tasks_loader)):
        return loader.load(self.id)

    # 后处理：在 tasks 加载完成后计算总任务数
    total_tasks: int = 0
    def post_total_tasks(self):
        return len(self.tasks)

# 使用 Resolver 解析数据
@app.get("/sprints", response_model=List[SprintResponse])
async def get_sprints():
    # 1. 从数据库获取基础数据
    sprints_data = await get_sprints_from_db()

    # 2. 转换为 Pydantic 模型
    sprints = [SprintResponse.model_validate(s) for s in sprints_data]

    # 3. Resolver 自动解析所有关联数据
    return await Resolver().resolve(sprints)
```

这个简单的例子展示了 pydantic-resolve 的核心威力。当你有多个 Sprint，每个 Sprint 有多个 Task，每个 Task 需要加载 owner 时，传统方式需要编写多层嵌套循环，而且很容易产生 N+1 查询。而使用 pydantic-resolve，你只需要声明数据依赖，框架会自动收集所有需要的 ID，合并成批量查询，然后将结果正确地填充到每个对象中。

DataLoader 的批量加载能力是这一切的"隐藏魔法"。假设你有 3 个 Sprint，每个 Sprint 有 10 个 Task，这些 Task 分别属于 5 个不同的用户。传统方式可能会执行 1 次 Sprint 查询 + 3 次 Task 查询 + 30 次 User 查询（如果忘记批量）。而 DataLoader 会自动将这些请求合并为 1 次 Sprint 查询 + 3 次 Task 查询 + 1 次 User 查询（通过 `WHERE id IN (...)`）。这不仅大大减少了数据库往返次数，也让你的代码不再需要手动管理批量查询的复杂性。

---

## 二、复杂数据结构 - Expose 和 Collector

### 跨层数据传递的挑战

在实际业务中，数据往往需要在父子节点之间双向流动。比如一个 Story 需要将自己的 name 传递给所有子 Task，让 Task 显示完整路径（"StoryName - TaskName"）。或者反过来，Story 需要收集所有 Task 的 owner，生成一个"相关开发者"列表。在传统代码中，这种跨层数据传递会让代码变得非常耦合——父节点需要知道子节点的需求，子节点需要知道父节点的结构，任何一方的改动都可能影响另一方。

pydantic-resolve 通过 `ExposeAs` 和 `Collector` 提供了优雅的解决方案。`ExposeAs` 让父节点可以向后代节点暴露数据，而不需要显式传递参数。`Collector` 让父节点可以从所有子节点收集数据，而不需要手动遍历和聚合。这两种机制让数据流动变得更加自然，也使得父子节点之间的耦合度大大降低。

### ExposeAs：父节点向子节点暴露数据

`ExposeAs` 让你可以将父节点的字段暴露给后代节点，子节点的 `resolve_` 或 `post_` 方法可以通过 `ancestor_context` 访问这些数据。这在需要将父节点上下文传递给子节点的场景非常有用。

```python
from pydantic_resolve import ExposeAs
from typing import Annotated

class StoryResponse(BaseModel):
    id: int
    # 将 name 暴露给子节点，别名为 story_name
    name: Annotated[str, ExposeAs('story_name')]

    tasks: List[TaskResponse] = []

class TaskResponse(BaseModel):
    id: int
    name: str

    # post 方法可以访问祖先节点暴露的数据
    full_name: str = ""
    def post_full_name(self, ancestor_context):
        # 获取父节点（Story）暴露的 story_name
        story_name = ancestor_context.get('story_name')
        return f"{story_name} - {self.name}"
```

在这个例子中，Story 的 name 字段被暴露为 `story_name`，所有子 Task 都可以在 `post_full_name` 方法中访问这个值。这样就不需要在 Task 创建时显式传递 story_name，减少了参数传递的复杂性。

### Collector：子节点向父节点收集数据

`Collector` 让父节点可以从所有子节点收集数据，常用于聚合子节点的信息。配合 `SendTo` 注解，子节点的特定字段可以被自动发送到父节点的收集器中。

```python
from pydantic_resolve import Collector, SendTo
from typing import Annotated

class TaskResponse(BaseModel):
    id: int
    owner_id: int

    # 加载 owner，并发送到父节点的 related_users 收集器
    owner: Annotated[Optional[UserResponse], SendTo('related_users')] = None
    def resolve_owner(self, loader=Loader(user_batch_loader)):
        return loader.load(self.owner_id)

class StoryResponse(BaseModel):
    id: int
    name: str

    tasks: List[TaskResponse] = []
    def resolve_tasks(self, loader=Loader(story_to_tasks_loader)):
        return loader.load(self.id)

    # 收集所有子节点的 owner
    related_users: List[UserResponse] = []
    def post_related_users(self, collector=Collector(alias='related_users')):
        # collector.values() 返回所有去重后的 UserResponse
        return collector.values()
```

在这个例子中，每个 Task 的 owner 会被自动发送到父节点 Story 的 `related_users` 收集器中。Story 的 `post_related_users` 方法会接收到所有去重后的用户列表。这对于"显示所有相关开发者"这样的业务场景非常有用，而且不需要手动编写遍历和去重的逻辑。

---

## 三、高级功能 - Application Layer 业务模型（Entity-First）

### ORM-First 的架构困境

大多数 FastAPI 项目都遵循着相似的模式：先定义 SQLAlchemy ORM 模型，然后基于这些模型创建 Pydantic schema。这种"ORM 先行、Pydantic 跟随"的模式如此普遍，以至于许多开发者从未质疑过它的合理性。但当我们深入分析这种模式的实际应用时，一些深层的问题开始浮现。

Pydantic schema 被动地复制 ORM 模型的字段定义，导致类型定义在两个地方重复。当数据库新增字段或修改字段类型时，你需要同时修改 ORM 模型和 Pydantic schema，很容易遗漏或产生不一致。更糟糕的是，业务概念被数据库结构深度渗透——API 暴露 `owner_id` 和 `reporter_id` 这样的数据库外键，而不是"负责人"和"报告人"这样的业务角色。前端开发者需要理解数据库设计才能使用 API，这违反了最少知道原则。

当数据来自多个源时，这种架构的问题更加明显。用户信息可能在 PostgreSQL 中，订单数据在 MongoDB 中，库存状态需要从 RPC 服务获取，推荐列表从 Redis 缓存读取。缺少统一的抽象层使得系统难以应对数据源的变化，每次数据源的迁移或升级都会牵一发而动全身。

### Entity-First：业务概念成为架构核心

Entity-First 架构的核心思想是：**领域模型是架构的核心，数据层只是实现细节**。业务实体（Entity）应该表达纯粹的领域概念，比如"用户"、"任务"、"项目"，而不是数据库表。这些实体定义了业务对象的结构和它们之间的关系，独立于任何技术实现。API 契约应该根据具体用例来设计，从领域模型中选择需要的字段，添加用例特有的计算字段和验证逻辑。

pydantic-resolve 为 Entity-First 架构提供了完整的工具支持。通过 ERD（实体关系图）统一管理实体关系，通过 DataLoader 模式自动优化数据获取、避免 N+1 查询，通过 DefineSubset 机制实现类型定义的复用和组合。更重要的是，它提供了自动的数据组装执行层，让开发者只需声明"需要什么数据"，而不必关心"如何获取和组装数据"。

```python
from pydantic_resolve import base_entity, Relationship, LoadBy, config_global_resolver, DefineSubset

# 1. 定义业务实体（不依赖 ORM）
BaseEntity = base_entity()

class UserEntity(BaseModel):
    """用户实体：表达业务概念"""
    id: int
    name: str
    email: str

class TaskEntity(BaseModel, BaseEntity):
    """任务实体：定义业务关系"""
    __relationships__ = [
        Relationship(
            field='owner_id',
            target_kls=UserEntity,
            loader=user_batch_loader  # 不关心从哪加载
        )
    ]
    id: int
    name: str
    owner_id: int
    estimate: int

class StoryEntity(BaseModel, BaseEntity):
    """故事实体"""
    __relationships__ = [
        Relationship(field='id', target_kls=list[TaskEntity], loader=story_to_tasks_loader)
    ]
    id: int
    name: str

# 2. 注册 ERD（关系集中管理）
config_global_resolver(BaseEntity.get_diagram())

# 3. 从 Entity 定义 API Response（选择字段 + 扩展）
class UserSummary(DefineSubset):
    __subset__ = (UserEntity, ('id', 'name'))

class TaskResponse(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'name', 'estimate'))

    # LoadBy 自动解析 owner，无需写 resolve 方法
    owner: Annotated[Optional[UserSummary], LoadBy('owner_id')] = None

class StoryResponse(DefineSubset):
    __subset__ = (StoryEntity, ('id', 'name'))

    # LoadBy 自动解析 tasks
    tasks: Annotated[List[TaskResponse], LoadBy('id')] = []

# 4. 使用（完全屏蔽数据库细节）
@app.get("/stories")
async def get_stories():
    # 获取主数据
    stories = await get_stories_from_db()

    # 转换并自动解析所有关联数据
    stories = [StoryResponse.model_validate(s) for s in stories]
    return await Resolver().resolve(stories)
```

`LoadBy` 的引入带来了显著的代码简化。在传统的 resolve 模式下，你需要在每个 Response 类中编写 `resolve_owner`、`resolve_tasks` 等方法，这些方法大多是重复的样板代码——获取 loader、调用 load 方法、返回结果。而使用 `LoadBy` 后，这些逻辑完全消失了。

`LoadBy('owner_id')` 这个简单的注解会自动查找 ERD 中定义的关系：`TaskEntity` 有一个 `owner_id` 字段，通过 `user_batch_loader` 关联到 `UserEntity`。Resolver 会自动使用这个 loader 来获取数据，你不需要编写任何 resolve 方法。这不仅减少了代码量，也让 Response 定义更加清晰——你只需要声明"这个字段需要通过 owner_id 加载"，而不需要关心"如何加载"。

更重要的是，当关系定义发生变化时，你只需要修改 ERD 中的 `Relationship` 配置，所有使用 `LoadBy` 的地方都会自动适配。比如将 `user_batch_loader` 替换为 `user_from_rpc_loader`，Response 代码完全不需要改动。这种集中式的配置管理让关系的维护变得异常简单。

这种分层架构的核心价值在于**稳定性和可演进性**。当数据库结构需要优化时（比如拆分大表、调整索引），只需要修改 Loader 的实现，Entity 和 Response 完全不受影响。当业务需求变化导致 API 契约需要调整时，只需要修改 Response 定义，Entity 和 Loader 保持不变。当业务逻辑演进需要新的实体关系时，只需要更新 ERD 定义，已有的数据访问逻辑可以保持稳定。

---

## 四、可视化 - FastAPI Voyager 集成

### 为什么需要可视化？

pydantic-resolve 的声明式方式让代码变得简洁，但也带来了一个挑战：数据流动的逻辑变得"隐形"了。当你看到一个 `LoadBy('owner_id')` 注解时，你知道它会自动解析，但你可能不清楚底层的加载链路、依赖关系和数据流向。在调试复杂的数据结构时，这种不可见性会增加理解成本。

fastapi-voyager 是专为 pydantic-resolve 设计的可视化工具，它将声明式的数据依赖变成可见的、可交互的图表。就像给代码装上了"X 光眼镜"，你可以一眼看出哪些字段是通过 resolve 加载的，哪些是通过 post 计算的，哪些数据是从父节点暴露来的，哪些是被子节点收集的。点击任意节点，就能高亮显示它的上游依赖和下游消费者，让数据流向一目了然。

### 快速开始

```bash
pip install fastapi-voyager
```

```python
from fastapi import FastAPI
from fastapi_voyager import create_voyager

app = FastAPI()

# 挂载 voyager 来可视化你的 API
app.mount('/voyager', create_voyager(
    app,
    enable_pydantic_resolve_meta=True,  # 显示 pydantic-resolve 元数据
    er_diagram=BaseEntity.get_diagram()  # 显示实体关系图（可选）
))
```

访问 `http://localhost:8000/voyager` 查看交互式可视化。

### 理解可视化

启用 `enable_pydantic_resolve_meta=True` 后，fastapi-voyager 使用颜色标记来显示 pydantic-resolve 操作：

- 🟢 **resolve** - 字段通过 `resolve_{field}` 方法或 `LoadBy` 加载
- 🔵 **post** - 字段通过 `post_{field}` 方法计算
- 🟣 **expose as** - 字段通过 `ExposeAs` 暴露给后代节点
- 🔴 **send to** - 字段通过 `SendTo` 发送到父节点的收集器
- ⚫ **collectors** - 字段通过 `Collector` 从子节点收集数据

这种颜色编码让你能够快速理解数据流动的方向和方式。当你看到一个 Task 模型的 `owner` 字段标记为绿色 resolve，你就知道这个字段会通过 DataLoader 自动加载。当你看到 Story 模型的 `related_users` 字段标记为黑色 collectors，你就知道这个字段会从所有子 Task 收集 owner 数据。

fastapi-voyager 的交互功能让调试变得更加轻松。点击任意模型，可以查看它的上游依赖（它需要什么数据）和下游消费者（谁依赖它）。双击节点可以跳转到源代码定义，方便快速定位。搜索功能可以让你快速找到特定模型并追踪其关系。配合 ERD 视图，你还可以看到实体级别的定义关系，从更高的层次理解系统的数据架构。

**在线演示**：[https://www.fastapi-voyager.top/voyager/?tag=sample_1](https://www.fastapi-voyager.top/voyager/?tag=sample_1)

**项目地址**：[github.com/allmonday/fastapi-voyager](https://github.com/allmonday/fastapi-voyager)

---

## 五、GraphQL 支持

pydantic-resolve 现在支持 GraphQL 查询接口，利用现有的 ERD 系统自动生成 Schema，并根据 GraphQL 查询动态创建 Pydantic 模型。

### 基本使用

`pydantic-resolve` 提供框架无关的 `GraphQLHandler`，你可以轻松集成到任何 web framework。

#### FastAPI 集成示例

```python
from fastapi import FastAPI, APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from pydantic_resolve import base_entity, config_global_resolver, query
from pydantic_resolve.graphql import GraphQLHandler, SchemaBuilder

app = FastAPI()

# 1. 定义 BaseEntity
BaseEntity = base_entity()

# 2. 定义带 @query 方法的 Entity
class UserEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(field='id', target_kls=list['Post'], loader=post_loader)
    ]
    id: int
    name: str
    email: str

    @query(name='users')
    async def get_all(cls, limit: int = 10) -> list['UserEntity']:
        return await fetch_users(limit=limit)

    @query(name='user')
    async def get_by_id(cls, id: int) -> Optional['UserEntity']:
        return await fetch_user(id=id)

# 3. 配置全局 resolver
config_global_resolver(BaseEntity.get_diagram())

# 4. 创建 GraphQL handler 和 schema builder
handler = GraphQLHandler(BaseEntity.get_diagram())
schema_builder = SchemaBuilder(BaseEntity.get_diagram())

# 5. 定义请求模型
class GraphQLRequest(BaseModel):
    query: str
    operationName: Optional[str] = None

# 6. 创建路由
router = APIRouter()

@router.post("/graphql")
async def graphql_endpoint(req: GraphQLRequest):
    result = await handler.execute(
        query=req.query,
    )
    return result

@router.get("/schema")
async def graphql_schema():
    schema_sdl = schema_builder.build_schema()
    return PlainTextResponse(schema_sdl)

app.include_router(router)
```

**其他框架集成指南** (Flask, Starlette, Django 等): [GraphQL 框架集成指南](./graphql-integration.zh.md)

### 查询示例

```graphql
# 获取所有用户
query {
  users {
    id
    name
    email
  }
}

# 获取单个用户及其文章
query {
  user(id: 1) {
    id
    name
    posts {
      title
      content
    }
  }
}
```

### 尝试 Demo

项目包含一个完整的 GraphQL Demo 应用：

```bash
# 安装依赖
pip install fastapi uvicorn graphql-core

# 启动服务器
uv run uvicorn demo.graphql.app:app --reload

# 测试查询
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ users { id name email } }"}'
```

完整文档请参考 [demo/graphql/README.md](demo/graphql/README.md)。

---

## 六、为什么不用 GraphQL？

虽然 pydantic-resolve 的灵感来自 GraphQL，但它更适合作为 BFF（Backend For Frontend）层的解决方案：

| 特性 | GraphQL | pydantic-resolve |
|------|---------|------------------|
| 性能 | 需要复杂的 DataLoader 配置 | 内置批量加载 |
| 类型安全 | 需要额外的工具链 | 原生 Pydantic 类型支持 |
| 学习曲线 | 陡峭（Schema、Resolver、Loader...） | 平缓（只需要 Pydantic） |
| 调试 | 困难 | 简单（标准的 Python 代码） |
| 集成 | 需要额外的服务器 | 无缝集成现有框架 |
| 灵活性 | 查询过于灵活，难以优化 | 明确的 API 契约 |

---

## 许可证

MIT License

## 作者

tangkikodo (allmonday@126.com)
