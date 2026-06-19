---
name: pydantic-resolve-3step
description: 基于 pydantic-resolve 的三阶段开发模式，用于构建从建模讨论到生产部署的完整项目。适用于需要使用 ER Diagram + ORM + DefineSubset 渐进式开发的场景。
argument-hint: "[项目路径] 创建三阶段项目的目标目录"
---

# pydantic-resolve 三阶段开发模式

基于 pydantic-resolve 的渐进式开发方法论。项目在一个 `src/` 目录下逐步演进，每个阶段在上一阶段基础上新增代码。

| Phase | 职责 | 产出 |
|-------|------|------|
| **Phase 0** | 需求确认 | 实体 + 关系 + 聚合根 + 用例方法（与用户反复确认） |
| **Phase 1** | Schema + ER Diagram + mock seed | ORM models + Entity DTOs + build_relationship + Voyager |
| **Phase 2** | 方法实现 + GraphQL | service/<domain>/methods.py + QueryConfig/MutationConfig + GraphQL |
| **Phase 3** | UseCase 响应组装 + MCP + REST | DefineSubset + AutoLoad + UseCaseService + REST + MCP |

## 核心原则

- **需求确认是 Phase 0，必须反复与用户确认后才能进入 Phase 1**（详见下方「Phase 0: 需求确认」）
- 非功能模块与业务模块解耦，业务概念不侵入基础设施层
- **每个 Phase 采用 V 型验收：先定义验收标准（V 降），再实现，最后回查验收（V 升）**
- **每个 Phase 实现完成后必须暂停，展示验收结果，等用户确认后再进入下一阶段**
- Phase 间递进：同一项目目录下逐步丰富，只新增不修改已有代码

### V 型验收模型（贯穿所有 Phase）

每个 Phase 的结构统一为三段：

```
┌──────────────────────────────────────────────┐
│ V 降：定义验收标准                              │
│   "在当前 Phase 开始之前，先定义什么算做完。"      │
│   写入 spec/<phase>.md 的"验收标准"部分            │
└──────────────────────────────────────────────┘
                      ↓
              ┌───────────────┐
              │   实现 Phase   │
              └───────────────┘
                      ↓
┌──────────────────────────────────────────────┐
│ V 升：逐条回查验收                             │
│   "一条一条对照验收标准，通过才可继续。"           │
│   用户逐条确认 → 写入 spec/<phase>.md             │
└──────────────────────────────────────────────┘
```

验收标准必须是**可观察、可操作的**——不写"代码健壮"，写"GraphiQL 中执行 X query 返回 Y"。

## Phase 0: 需求确认（必做）

在写任何代码之前，必须与用户逐项确认以下内容。每一项都需要用户明确认可后才算完成。

### Step 0-1: 术语与实体定义

逐一列出所有业务实体，每个实体说明：

- **业务含义**（一句话，团队无歧义）
- **核心字段**（名称 + 类型 + 语义说明，不需要穷举，但关键属性不能遗漏）
- **字段约束**（唯一、非空、枚举值、联合唯一等）

用表格形式呈现，方便用户逐行确认。

### Step 0-2: 实体关系

用文本 ER 图展示实体间关系，每条关系标明：

- 方向（1:N / N:1 / M:N）
- 业务含义（如「Sprint 包含多条 Task」）
- 是否需要中间实体

```
User ──1:N──→ Task
Sprint ──1:N──→ Task
Task ──N:1──→ User (owner)
```

**必须与用户确认关系方向和基数是否正确。**

### Step 0-3: 聚合根

明确哪个（或哪些）实体是聚合根。聚合根决定：

- 主要的业务入口（从哪个实体开始查询）
- @query / @mutation 挂在哪些实体上
- Phase 3 的 service 划分依据

### Step 0-4: 业务域划分 + 用例方法

**⚠️ 禁止自行决定 Service 切分方案。必须提出候选方案与用户讨论，由用户最终确认。**

#### Step 0-4a: 提出 Service 切分候选方案

业务域（Service）按功能边界划分，不按实体划分。Service 切分直接影响：
- 目录结构（`service/<domain>/`）
- Phase 2 的 methods.py 粒度
- Phase 3 的 UseCaseService 类划分
- MCP 和 REST 的入口组织

**必须向用户提出至少一种候选方案**，说明每种方案的切分依据和优劣，由用户选择或修正。

常见的切分策略参考：

| 策略 | 示例 | 适用场景 |
|------|------|----------|
| 按业务功能域 | `auth` / `chat` / `order` | 业务边界清晰，领域间耦合低 |
| 按聚合根 | `user` / `conversation` / `message` | 实体独立性强，CRUD 为主 |
| 混合（功能域 + 独立聚合） | `auth` / `chat`(含 conversation+message) | 部分域跨实体协作 |

#### Step 0-4b: 按确认的 Service 划分列出用例方法

用户确认 Service 切分后，按每个业务域列出用例方法。每个方法说明：

- **方法名**（动词开头，如 `list_sprints`、`create_task`）
- **业务意图**（一句话）
- **关键参数**（列出参数名和含义）

示例格式：

| 业务域 | 方法名 | 业务意图 | 关键参数 |
|--------|--------|----------|----------|
| sprint | list_sprints | 获取所有 Sprint | - |
| sprint | get_sprint | 获取单个 Sprint | sprint_id |
| task | list_tasks | 获取所有任务 | - |
| task | get_tasks_by_sprint | 按 Sprint 查任务 | sprint_id |
| task | create_task | 创建任务 | title, sprint_id, owner_id |

### Step 0-5: GraphQL 定位

GraphQL 是辅助开发测试和 AI 测试的接口，不是正式 API。

业务方法的定义和挂载关系：

```
service/<domain>/methods.py  ← 独立定义业务逻辑（核心）
        ↓ 挂载
  Entity via QueryConfig/MutationConfig
  (GraphQL 辅助测试)

  Phase 3: 同一个方法在 UseCaseService 中调用（REST/MCP 使用）
```

- Phase 2：方法体在 `service/<domain>/methods.py` 中实现，通过 `QueryConfig`/`MutationConfig` 绑定到 ErDiagram 的 Entity
- Phase 3：同一个方法在 UseCaseService 中调用（REST/MCP 使用），DTO 转换在 Service 层完成

### Step 0-6: 第三方库确认

列出项目中涉及的非业务功能领域，对每个领域：

- **说明候选方案**
- **给出推荐理由**
- **必须调查用户提到的第三方库的当前维护状态**

| 功能领域 | 推荐方案 | 理由 | 备注 |
|----------|----------|------|------|
| ORM | SQLAlchemy 2.0 async | 成熟、pydantic-resolve 原生支持 build_relationship | - |
| 可视化 | fastapi-voyager | ER diagram 可视化 | `pip install fastapi-voyager` |
| MCP | fastmcp>=3.2.4 | pydantic-resolve 原生支持 | - |

**对于 pydantic-resolve 已覆盖的领域（ORM 集成、GraphQL、MCP），不再重复讨论。**

### Step 0-7: 检查清单

全部确认后，向用户展示汇总：

- [ ] 所有实体和字段是否完整，约束是否清晰？
- [ ] 实体关系方向和基数是否正确？
- [ ] 聚合根是否明确？
- [ ] **Service 切分方案是否由用户确认？**
- [ ] 核心用例是否覆盖主要业务场景？
- [ ] 第三方库选型是否确认？
- [ ] 是否有明显的遗漏或边界情况？

**全部确认后才能进入 Phase 1。**

## 参考实现

读取本 skill 目录下 `template/` 中的代码作为生成参考。严格遵守 template 中的文件结构、import 风格和命名约定。

## 项目结构

单项目渐进演进，每个 Phase 在上一阶段基础上新增文件：

```
src/
├── db.py           # Phase 1（engine + session_factory，不依赖 models）
├── models.py       # Phase 1 SQLAlchemy ORM models（纯字段 + relationship）
├── entities.py     # Phase 1 Pydantic Entity DTOs + ErDiagram → Phase 2 新增 QueryConfig
├── database.py     # Phase 1（mock seed，依赖 db + models）
├── main.py         # 逐步扩展（voyager → graphql → rest → mcp）
├── service/        # Phase 2 新增 methods.py，Phase 3 补充 service.py/dtos.py
│   ├── sprint/
│   │   ├── methods.py  # Phase 2: 独立业务方法
│   │   ├── dtos.py     # Phase 3: DefineSubset DTOs
│   │   ├── service.py  # Phase 3: UseCaseService
│   │   └── spec.md     # Phase 3: 服务说明
│   ├── task/
│   │   ├── methods.py
│   │   ├── dtos.py
│   │   ├── service.py
│   │   └── spec.md
│   └── user/
│       └── methods.py
├── router/
│   └── api.py      # Phase 3: 手写 REST 路由
```

## 三阶段定义

### Phase 1: Schema + ER Diagram + mock seed

**目标**: 定义 ORM models + Pydantic Entity DTOs + `build_relationship()` + mock seed data，用 Voyager 可视化供团队讨论。**不含任何业务方法**。

**新增/修改文件**:
- `db.py` — aiosqlite engine + session_factory（不导入 models，避免循环依赖）
- `models.py` — SQLAlchemy ORM models（纯字段 + relationship，加 `lazy="noload"`）
- `entities.py` — Pydantic Entity DTOs (`from_attributes=True`) + `build_relationship()` + ErDiagram + `config_resolver()`
- `database.py` — mock seed data（从 `db.py` 导入 engine/session，从 `models.py` 导入实体）
- `main.py` — FastAPI + Voyager（ER diagram 可视化）

**关键模式**:
- **ORM Model 和 Entity DTO 分离**：ORM Model 是 SQLAlchemy `DeclarativeBase` 子类，Entity DTO 是 Pydantic `BaseModel` 子类（加 `model_config = ConfigDict(from_attributes=True)`）
- `build_relationship(mappings=[Mapping(entity=..., orm=...)], session_factory=...)` 从 ORM 元数据自动生成所有 DataLoader
- `ErDiagram(entities=[]).add_relationship(entities)` 创建空 ErDiagram 后追加自动生成的关系
- `config_resolver("MyResolver", er_diagram=diagram)` 创建与 ErDiagram 绑定的 Resolver class
- ORM Model 的 relationship 全部加 `lazy="noload"`，不依赖 ORM 懒加载
- Voyager 使用 `fastapi-voyager` 的 `create_voyager(app, er_diagram=diagram)`
- Phase 1 无 GraphiQL（无方法可查询），GraphQL 在 Phase 2 后可用

```python
# db.py
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

engine = create_async_engine("sqlite+aiosqlite://", echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

def session_factory():
    return async_session_factory()
```

```python
# models.py — 纯 ORM
from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class UserOrm(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    tasks: Mapped[list["TaskOrm"]] = relationship(back_populates="owner", lazy="noload")
```

```python
# entities.py — Pydantic DTOs + ErDiagram
from pydantic import BaseModel, ConfigDict
from pydantic_resolve import ErDiagram, config_resolver
from pydantic_resolve.integration.mapping import Mapping
from pydantic_resolve.integration.sqlalchemy import build_relationship
from src.db import session_factory
from src.models import UserOrm, TaskOrm, SprintOrm

class UserEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

# ... other entities ...

auto_entities = build_relationship(
    mappings=[
        Mapping(entity=UserEntity, orm=UserOrm),
        Mapping(entity=TaskEntity, orm=TaskOrm),
        Mapping(entity=SprintEntity, orm=SprintOrm),
    ],
    session_factory=session_factory,
)

diagram = ErDiagram(entities=[]).add_relationship(auto_entities)
MyResolver = config_resolver("MyResolver", er_diagram=diagram)
```

**V 降 — 定义验收标准:**
进入 Phase 1 实现之前，在 `spec/phase1.md` 中记录验收标准：

| # | 验收项 | 验证方式 |
|---|--------|----------|
| 1 | 每个 Entity 在 Voyager ER 图中正确显示，关系线方向正确 | 浏览器打开 Voyager |
| 2 | `models.py` 中每个 ORM Model 只包含字段 + relationship，无业务方法 | 检查代码结构 |
| 3 | `entities.py` 中每个 Entity DTO 有 `from_attributes=True` | 检查代码 |
| 4 | mock seed 数据样本展示合理的数量、关联关系 | 编写简单查询验证 |

**V 升 — 逐条回查验收:**
- [ ] 1. Voyager ER 图：实体节点、关系线
- [ ] 2. ORM Model 纯字段：无业务方法
- [ ] 3. Entity DTO from_attributes=True
- [ ] 4. mock seed：数据量合理、关联关系正确

### Phase 2: 方法实现 + Entity 挂载

**目标**: 按业务域实现独立方法，通过 `QueryConfig`/`MutationConfig` 绑定到 Entity，GraphQL 可查询。

**新增/修改文件**:
- `service/<domain>/methods.py` — 独立业务方法实现（直接操作 session + ORM model）
- `entities.py` — 新增 `QueryConfig`/`MutationConfig` 绑定

**关键模式**:
- **业务方法在 `service/<domain>/methods.py` 中定义**，为普通 async 函数（直接操作 SQLAlchemy session + ORM model，不含 `cls` 参数）
- **通过 `QueryConfig`/`MutationConfig` 在 ErDiagram 层面绑定**到 Entity（不需要 `mount_method()` + `_mount()` 桥接模式）
- `QueryConfig(method=list_sprints, name="sprints")` 中 method 是独立函数，name 是 GraphQL 查询名
- **GraphQLHandler 接收 `er_diagram=diagram`**（不是 base + session_factory）
- **config_resolver 必须在 build_relationship 之后调用**
- **GraphQLHandler 必须在 ErDiagram 完整配置（含 QueryConfig/MutationConfig）之后创建**

```python
# service/sprint/methods.py
from sqlalchemy import select
from src.db import session_factory
from src.models import SprintOrm

async def list_sprints() -> list[SprintOrm]:
    """获取所有 Sprint。"""
    async with session_factory() as session:
        result = await session.execute(select(SprintOrm).order_by(SprintOrm.id))
        return list(result.scalars().all())
```

```python
# entities.py — 新增 QueryConfig/MutationConfig（Phase 2 新增部分）
from pydantic_resolve import Entity, QueryConfig, MutationConfig
from src.service.sprint.methods import list_sprints, get_sprint, create_sprint

query_mutation_entities = [
    Entity(kls=SprintEntity, queries=[
        QueryConfig(method=list_sprints, name="sprints"),
        QueryConfig(method=get_sprint, name="sprint"),
    ], mutations=[
        MutationConfig(method=create_sprint, name="create_sprint"),
    ]),
    # ... other entities ...
]

diagram = (
    ErDiagram(entities=[])
    .add_relationship(auto_entities)
    .add_relationship(query_mutation_entities)
)
MyResolver = config_resolver("MyResolver", er_diagram=diagram)
```

**V 降 — 定义验收标准:**
进入 Phase 2 编码之前，先与用户确认测试验收集并写入 `spec/phase2.md`：

| # | 方法 | 测试场景 | 预期结果 | 验证方式 |
|---|------|----------|----------|----------|
| 1 | list_sprints | 查询所有 | 返回 seed 数据 | GraphiQL query |
| 2 | create_sprint | 创建新 Sprint | 返回新 Sprint | GraphiQL mutation |
| 3 | tasks_by_sprint | 按 sprint 查任务 | 返回正确过滤结果 | GraphiQL query |
| ... | ... | ... | ... | ... |

验收标准要求：
- 每个 query/mutation 至少覆盖：**一个正常场景**
- 验证方式统一通过 GraphQL query/mutation 在 GraphiQL 中执行

**V 升 — 逐条回查验收:**
启动服务，在 GraphiQL 中逐一执行验收表：

- [ ] 1. list_sprints → 返回 seed 数据
- [ ] 2. create_sprint → 返回新 Sprint 对象
- [ ] 3. tasks_by_sprint → 返回过滤后的任务列表
- [ ] ...（每条对标验收表）
- [ ] 确认 seed 数据仍可查询，Loader 行为符合预期

### Phase 3: UseCase 响应组装 + MCP + REST

**目标**: 按 API 用例组装响应结构。DefineSubset 隐藏内部字段，AutoLoad 自动加载关系，UseCaseService 统一业务入口，REST 端点对外暴露。

**新增/修改文件**:
- `service/<domain>/spec.md` — 服务目的、用途、需求、变更记录
- `service/<domain>/dtos.py` — DefineSubset DTOs + AutoLoad + post_*
- `service/<domain>/service.py` — UseCaseService
- `router/api.py` — 手写 REST 路由
- `main.py` — 新增 REST + MCP

**关键模式**:
- **DefineSubset 使用元组形式**：`__subset__ = (Entity, ['id', 'name'])`
- **AutoLoad 用 `origin` 参数映射关系名**：`Annotated[UserSummary | None, AutoLoad(origin="owner")] = None`
- **AutoLoad 字段用基础 Entity 类型**（不用 DefineSubset 类型），避免 from_attributes 访问未加载的 ORM relationship 导致 DetachedInstanceError
- **UseCaseService 复用 methods.py 的核心逻辑**，不重新实现：
  - list 方法：调 methods 拿 `list[OrmModel]` → `[Dto.model_validate(m) for m in models]` → `MyResolver(enable_from_attribute_in_type_adapter=True).resolve(dtos)`
  - get 单条：调 methods 拿 `OrmModel | None` → `Dto.model_validate(entity)` → `(await MyResolver(...).resolve([dto]))[0]`
- **手写 REST 路由**（没有 `create_use_case_router()`）
- **`enable_from_attribute_in_type_adapter=True`** 在从 ORM 转换时必须设置
- MCP 使用 `create_use_case_graphql_mcp_server()` + `UseCaseAppConfig`
- MCP http_app 使用 `transport="streamable-http", stateless_http=True`

```python
# service/task/dtos.py
from typing import Annotated
from pydantic_resolve import DefineSubset, AutoLoad
from src.entities import UserEntity, TaskEntity

class UserSummary(DefineSubset):
    __subset__ = (UserEntity, ["id", "name"])

class TaskSummary(DefineSubset):
    __subset__ = (TaskEntity, ["id", "title", "done"])
    owner_detail: Annotated[UserSummary | None, AutoLoad(origin="owner")] = None
```

```python
# service/sprint/dtos.py
from pydantic_resolve import DefineSubset, AutoLoad
from src.entities import SprintEntity, TaskEntity
from src.service.task.dtos import TaskSummary

class SprintSummary(DefineSubset):
    __subset__ = (SprintEntity, ["id", "name"])
    task_list: Annotated[list[TaskEntity], AutoLoad(origin="tasks")] = []
    task_count: int = 0
    contributor_names: list[str] = []

    def post_task_count(self):
        return len(self.task_list)

    def post_contributor_names(self):
        return sorted({t.owner.name for t in self.task_list if t.owner})
```

```python
# service/task/service.py
from pydantic_resolve import query
from pydantic_resolve.use_case import UseCaseService
from src.entities import MyResolver
from src.service.task.dtos import TaskSummary
from src.service.task.methods import list_tasks as _list_tasks

class TaskService(UseCaseService):
    @query
    async def list_tasks(cls) -> list[TaskSummary]:
        tasks = await _list_tasks()
        dtos = [TaskSummary.model_validate(t) for t in tasks]
        return await MyResolver(enable_from_attribute_in_type_adapter=True).resolve(dtos)
```

```python
# router/api.py
from fastapi import APIRouter, HTTPException
from src.service.sprint.service import SprintService
from src.service.task.service import TaskService

route = APIRouter(prefix="/api")

@route.get("/tasks", tags=[TaskService.get_tag_name()])
async def get_tasks():
    return await TaskService.list_tasks()

@route.get("/sprints", tags=[SprintService.get_tag_name()])
async def get_sprints():
    return await SprintService.list_sprints()
```

**V 降 — 定义验收标准:**

| # | 验收项 | 验证方式 |
|---|--------|----------|
| 1 | REST 端点返回的响应字段符合 DTO 定义（FK 隐藏、关系字段包含） | curl GET endpoint |
| 2 | MCP 四层渐进式披露完整：discover → inspect → execute | MCP 客户端调用 |
| 3 | GraphQL 查询仍然正常工作 | GraphiQL |

**V 升 — 逐条回查验收:**

- [ ] 1. REST：`curl /api/tasks` 返回字段符合 TaskSummary DTO，不含 sprint_id/owner_id
- [ ] 2. REST：`curl /api/sprints` 返回 SprintSummary 含 task_count 和 contributor_names
- [ ] 3. MCP：依次调用 list_apps → describe_compose_schema → describe_compose_method → compose_query
- [ ] 4. GraphQL：list_sprints 返回相同数据

## 阶段间变化对照

| 方面 | Phase 1 | Phase 2 | Phase 3 |
|------|---------|---------|---------|
| ORM Model | 纯字段 + relationship (noload) | 不变 | 不变 |
| Entity DTO | from_attributes=True | 新增 QueryConfig/MutationConfig | 继承 |
| 关系 | build_relationship() 自动生成 | 不变 | DefineSubset 隐藏 FK |
| 查询函数 | 无方法 | methods.py + QueryConfig | UseCaseService 封装（复用 methods.py） |
| API | Voyager(ER diagram) | GraphQL | GraphQL + REST + MCP |
| 响应 | N/A | 完整实体 | DefineSubset DTO |

## 踩坑经验

1. **engine/session 必须独立为 `db.py`** — `models.py` 和 `database.py` 都需要 session，放在同一文件会导致循环导入
2. **`pyproject.toml` 必须配置 `packages = ["src"]`** — hatchling 需要 `[tool.hatch.build.targets.wheel]`
3. **不要在 DefineSubset 文件中使用 `from __future__ import annotations`** — 会使类型注解变字符串，SubsetMeta 无法检测 Annotated 元数据，FK 字段不会被自动添加
4. **AutoLoad 字段用基础 Entity 类型，不用 DefineSubset 类型** — build_relationship 的 DataLoader 返回 ORM 对象。DefineSubset 类型带 `from_attributes=True` 会尝试访问所有 ORM 属性（包括未加载的 relationship），导致 `DetachedInstanceError`
5. **`build_relationship` 需要 Entity 有 `from_attributes=True`** — `Mapping` 验证 Entity 的 `model_config` 必须包含 `from_attributes=True`
6. **`config_resolver` 必须在 `build_relationship` 之后调用** — resolver 需要完整的 ErDiagram
7. **`GraphQLHandler` 必须在 ErDiagram 完整配置后创建** — handler 初始化时扫描 Entity 的 query/mutation 方法
8. **目录命名不能以数字开头** — Python 模块名限制
9. **UseCaseService 方法必须声明返回类型注解** — MCP 和 FastAPI 的 response_model 提取依赖返回类型
10. **单条 get 模式**：`resolve([dto])` 后取 `[0]` — Resolver 只接受 list
11. **`enable_from_attribute_in_type_adapter=True` 在从 ORM 转换时需要** — 否则 DataLoader 返回的 ORM 对象无法被 TypeAdapter 正确处理
12. **所有 ORM relationship 加 `lazy="noload"`** — 不依赖 ORM lazy-load，避免 session 关闭后 DetachedInstanceError
13. **methods.py 返回 ORM Model，service.py 负责 DTO 转换** — methods.py 是纯业务逻辑层，返回 ORM 实体。service.py 统一调用 methods.py，DTO 转换和 Resolver().resolve() 在 service.py 中进行
14. **fastmcp>=3.2.4 挂载到 FastAPI 需要 lifespan 合并** — 必须使用 `transport="streamable-http", stateless_http=True`，在 FastAPI lifespan 中嵌套 MCP http_app 的 lifespan
15. **`QueryConfig` 的 name 参数不是最终 GraphQL 查询名** — 实际名称格式为 `{EntityName}{NameCamel}`，如 `QueryConfig(method=list_sprints, name="sprints")` 对应 `sprintEntitySprints`
16. **DefineSubset 中 AutoLoad 字段名可以与 relationship name 不同** — 使用 `AutoLoad(origin="relationship_name")` 映射
17. **`GraphQLHandler.execute()` 只接受 `query` 和 `context`** — 不接受 `variables` 和 `operation_name`，与 sqlmodel-nexus 不同

## 需求文档管理

每次使用 skill 时，必须在项目根目录下创建 `spec/` 目录：

### 目录命名

```
spec/<编号>-<需求简述>/
```

- **编号格式**: `YY-MM-DD` + 两位序号，如 `250510-01`
- **需求简述**: 英文短横线连接

示例: `spec/250510-01-sprint-demo/`

### 文件结构

```
spec/<编号>-<需求简述>/
├── story.md        # 用户原始需求 + Overview Design
├── phase0.md       # 需求确认
├── phase1.md       # Schema + ER Diagram
├── phase2.md       # 方法实现 + GraphQL
└── phase3.md       # UseCase + MCP + REST
```

### 文件内容格式

每个 phase 文件分三个部分：

```markdown
# Phase N: <阶段标题>

## 需求说明
（记录用户在对话中提出的原始需求、约束条件和确认结论）

## 验收标准
（V 降阶段定义的验收标准表格）

## 实现描述
（记录技术实现方案、产出文件、关键决策和 V 升回查结果）
```

### 写入时机

| 文件 | 写入时机 |
|------|----------|
| story.md | 用户首次描述需求时记录原始表述；Phase 0 确认后补充 Overview Design |
| phase0.md | Phase 0 全部确认后 |
| phase1.md | V 降 → 实现 → V 升通过后 |
| phase2.md | V 降 → 实现 → V 升通过后 |
| phase3.md | V 降 → 实现 → V 升通过后 |

## 执行步骤

当用户要求创建三阶段项目时：

1. **创建 spec 目录**: 用户首次描述需求时创建 `spec/<编号>-<需求简述>/`，将原始需求写入 `story.md`
2. **Phase 0 需求确认**: 按 Step 0-1 ~ 0-7 逐步确认 → 写入 `phase0.md` → 补充 `story.md` 的 Overview Design
3. **创建项目结构**: 目录 + pyproject.toml（依赖 pydantic-resolve, fastapi, sqlalchemy, aiosqlite 等）
4. **Phase 1**:
   - **V 降**: 确认验收标准写入 `spec/phase1.md#验收标准`
   - **实现**: db.py → models.py → entities.py → database.py → main.py
   - **V 升**: 逐条验收 → 通过后写入 `phase1.md` → **暂停等用户确认**
5. **Phase 2**:
   - **V 降**: 确认测试验收集写入 `spec/phase2.md#验收标准`
   - **实现**: service/<domain>/methods.py → entities.py 新增 QueryConfig/MutationConfig → main.py 新增 GraphQL
   - **V 升**: GraphiQL 逐一执行 → 通过后写入 `phase2.md` → **暂停等用户确认**
6. **Phase 3**:
   - **V 降**: 确认验收标准写入 `spec/phase3.md#验收标准`
   - **实现**: dtos.py → service.py → router/api.py → main.py 新增 REST + MCP
   - **V 升**: 测试 REST + MCP + GraphQL → 通过后写入 `phase3.md` → **暂停等用户确认**

### story.md 的 Overview Design 部分

Phase 0 全部确认后、进入 Phase 1 之前，在 `story.md` 中补充 `## Overview Design`：

- **业务流程**：核心用户操作路径
- **实体关系**：ER 图（文本格式）
- **聚合根**：明确入口实体
- **关键设计决策**：第三方库选型等
- **三阶段产出**：每个 Phase 的预期交付物概要
