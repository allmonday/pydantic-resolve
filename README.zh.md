# Pydantic Resolve

> 基于 Pydantic 的声明式数据组装工具 —— 用最少的代码消除 N+1 查询。

[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![PyPI Downloads](https://static.pepy.tech/badge/pydantic-resolve/month)](https://pepy.tech/projects/pydantic-resolve)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)

[English](./README.md)

![](./docs/images/features.png)

---

**pydantic-resolve** 受 GraphQL 启发。它基于 DataLoader 构建与数据库无关的应用层实体关系图，提供丰富的数据组装和后处理能力，并能自动生成 GraphQL 查询和 MCP 服务。

## 为什么选择 pydantic-resolve？

**核心能力：**

| 特性 | 说明 |
|------|------|
| **自动批量加载** | DataLoader 自动消除 N+1 查询 |
| **声明式组装** | 声明依赖关系，框架自动处理 |
| **Entity-First 架构** | ER Diagram 定义关系，`AutoLoad` 自动解析 |
| **GraphQL 支持** | 从 ERD 生成 Schema，动态模型查询 |
| **MCP 集成** | 将 GraphQL API 暴露给 AI 代理，支持渐进式披露 |

**一行代码获取嵌套数据：**

```python
class Task(BaseModel):
    owner_id: int
    owner: Optional[User] = None

    def resolve_owner(self, loader=Loader(user_loader)):
        return loader.load(self.owner_id)  # 就这么简单！

# Resolver 自动将所有 owner 查询合并为一次批量查询
result = await Resolver().resolve(tasks)
```

---

## 快速开始

### 安装

```bash
pip install pydantic-resolve
```

### N+1 问题

```python
# 传统方式：1 + N 次查询
for task in tasks:
    task.owner = await get_user(task.owner_id)  # N 次查询！
```

### pydantic-resolve 解决方案

```python
from pydantic import BaseModel
from typing import Optional, List
from pydantic_resolve import Resolver, Loader, build_list

# 1. 定义 loader（批量查询）
async def user_loader(ids: list[int]):
    users = await db.query(User).filter(User.id.in_(ids)).all()
    return build_list(users, ids, lambda u: u.id)

async def task_loader(sprint_ids: list[int]):
    tasks = await db.query(Task).filter(Task.sprint_id.in_(sprint_ids)).all()
    return build_list(tasks, sprint_ids, lambda t: t.sprint_id)

# 2. 定义带 resolve 方法的 schema
class TaskResponse(BaseModel):
    id: int
    name: str
    owner_id: int

    owner: Optional[dict] = None
    def resolve_owner(self, loader=Loader(user_loader)):
        return loader.load(self.owner_id)

class SprintResponse(BaseModel):
    id: int
    name: str

    tasks: List[TaskResponse] = []
    def resolve_tasks(self, loader=Loader(task_loader)):
        return loader.load(self.id)

# 3. Resolve - 框架自动处理批量查询
@app.get("/sprints")
async def get_sprints():
    sprints = await get_sprint_data()
    return await Resolver().resolve([SprintResponse.model_validate(s) for s in sprints])
```

**结果：** 每个 loader 只执行 1 次查询，无论数据深度如何。

---

## 核心概念

### Resolve：声明式数据加载

告别命令式数据获取，声明你需要什么：

```python
class Task(BaseModel):
    owner_id: int
    owner: Optional[User] = None

    def resolve_owner(self, loader=Loader(user_loader)):
        return loader.load(self.owner_id)
```

框架会：
1. 收集所有 `owner_id` 值
2. 合并为一次批量查询
3. 将结果映射回正确的对象

### DataLoader：自动批量优化

DataLoader 在同一个事件循环周期内自动合并多个请求：

```python
# 没有 DataLoader：100 个 task = 100 次 user 查询
# 使用 DataLoader：100 个 task = 1 次 user 查询 (WHERE id IN (...))

async def user_loader(user_ids: list[int]):
    return await db.query(User).filter(User.id.in_(user_ids)).all()
```

### Expose & Collect：跨层数据流

在嵌套数据结构中，父子节点经常需要共享数据。传统方式需要显式传参或紧耦合。pydantic-resolve 提供两种声明式机制：

- **ExposeAs**：父节点向所有后代暴露数据（向下流动）
- **SendTo + Collector**：子节点向父节点收集器发送数据（向上流动）

这实现了清晰的分离 —— 父节点不需要知道子节点的结构，子节点也不需要显式的父节点引用。

```python
from pydantic_resolve import ExposeAs, Collector, SendTo
from typing import Annotated

# 1. 父节点 EXPOSE 数据给后代（向下流动）
class Story(BaseModel):
    name: Annotated[str, ExposeAs('story_name')]
    tasks: List[Task] = []

# 2. 子节点访问祖先上下文（无需显式父节点引用）
class Task(BaseModel):
    def post_full_path(self, ancestor_context):
        return f"{ancestor_context['story_name']} / {self.name}"

# 3. 子节点发送数据到父节点收集器（向上流动）
class Task(BaseModel):
    owner: Annotated[User, SendTo('contributors')] = None

class Story(BaseModel):
    contributors: List[User] = []
    def post_contributors(self, collector=Collector('contributors')):
        return collector.values()  # 自动去重的所有 task owner 列表
```

**使用场景：**
- 向下传递配置/上下文（如用户权限、语言设置）
- 向上聚合结果（如收集所有文章的唯一标签）

---

## 高级特性

### Entity-First 架构

定义独立于数据库 schema 的业务实体。

**为什么选择 Entity-First 而非 DB-based 关系？**

| 方面 | DB-based (ORM) | Entity-First (pydantic-resolve) |
|------|----------------|--------------------------------|
| **灵活性** | 绑定数据库 schema | 在应用层定义关系 |
| **数据源** | 单一数据库 | 跨多数据源（PostgreSQL、MongoDB、Redis、RPC） |
| **封装性** | 暴露 FK 字段（`owner_id`） | Loader 实现对 API 隐藏 |
| **API 契约** | DB 变化时 API 跟着变 | 稳定，与存储解耦 |

```python
from pydantic_resolve import base_entity, Relationship, AutoLoad

BaseEntity = base_entity()

# Entity 定义业务关系，而非数据库 FK
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        # Loader 可以查询 Postgres、调用 RPC、或从 Redis 获取
        # API 消费者不需要知道数据从哪来
        Relationship(field='owner_id', target_kls=UserEntity, loader=user_loader)
    ]
    id: int
    name: str
    description: Optional[str] = None
    status: str  # todo, in_progress, done
    owner_id: int  # 内部 FK，可以对 API 隐藏

# Response schema：选择要暴露的内容
class TaskResponse(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'name'))  # owner_id 被排除
    owner: Annotated[User, AutoLoad('owner_id')] = None  # 自动解析！
```

**核心优势：**
- 更换 loader 实现（SQL → RPC）无需修改 Response 代码
- 在单个实体图中混合多个数据源
- 隐藏内部 ID，只暴露业务概念

[→ 完整 Entity-First 指南](https://allmonday.github.io/pydantic-resolve/erd_driven/)

### GraphQL 支持

从 ERD 生成 GraphQL schema：

```python
from pydantic_resolve.graphql import GraphQLHandler

handler = GraphQLHandler(BaseEntity.get_diagram())
result = await handler.execute("{ users { id name posts { title } } }")
```

[→ GraphQL 文档](./demo/graphql/README.md)

### MCP 集成

将 GraphQL API 暴露给 AI 代理，支持渐进式披露：

```python
from pydantic_resolve.graphql.mcp import create_mcp_server

mcp = create_mcp_server(apps=[AppConfig(name="blog", er_diagram=diagram)])
mcp.run()  # AI 代理现在可以发现并查询你的 API
```

[→ MCP 文档](https://allmonday.github.io/pydantic-resolve/api/)

### 可视化

使用 [fastapi-voyager](https://github.com/allmonday/fastapi-voyager) 进行交互式 schema 探索：

```python
from fastapi_voyager import create_voyager

app.mount('/voyager', create_voyager(app, er_diagram=BaseEntity.get_diagram()))
```

---

## pydantic-resolve vs GraphQL

| 特性 | GraphQL | pydantic-resolve |
|------|---------|------------------|
| **N+1 预防** | 手动 DataLoader 配置 | 内置自动批量加载 |
| **类型安全** | 需要额外的 schema 文件 | 原生 Pydantic 类型 |
| **学习曲线** | 陡峭（Schema、Resolvers、Loaders） | 平缓（只需要 Pydantic） |
| **调试** | 复杂的内省 | 标准 Python 调试 |
| **集成** | 需要专用服务器 | 可与任何框架集成 |
| **查询灵活性** | 任何客户端可以查询任何内容 | 明确的 API 契约 |

---

## 资源

- 📖 [完整文档](https://allmonday.github.io/pydantic-resolve/)
- 🚀 [示例项目](https://github.com/allmonday/composition-oriented-development-pattern)
- 🎮 [在线演示](https://www.fastapi-voyager.top/voyager/)
- 📚 [API 参考](https://allmonday.github.io/pydantic-resolve/api/)

---

## 许可证

MIT License

## 作者

tangkikodo (allmonday@126.com)
