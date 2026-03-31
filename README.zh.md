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
| **ER Diagram + AutoLoad** | 定义实体关系，自动解析关联数据 |
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

## 声明式模式：ER Diagram + AutoLoad

快速开始和核心概念展示的是 pydantic-resolve 的 **Core API**：手写 `resolve_*` 方法，手动指定 Loader。对于简单场景这已经足够。

当项目中有多个互相关联的实体时，pydantic-resolve 提供了 **Declarative API**：在 ER Diagram 中集中定义实体关系和默认 Loader，然后通过 `AutoLoad` 自动生成对应的 resolve 方法。

Declarative API 的底层就是 Core API。`AutoLoad` 字段在运行时会生成等价的 `resolve_*` 方法，因此两种模式可以自由混用——在 Declarative Mode 下，你仍然可以使用 `post_*` 方法，也可以对某些字段回退到手写 `resolve_*`。

| | Core API | Declarative API |
|--|----------|-----------------|
| **做法** | 手写 `resolve_*` + 指定 `Loader` | 定义 ER Diagram + `AutoLoad` |
| **控制度** | 完全控制 | 约定优于配置 |
| **适合场景** | 简单项目、一次性数据加载 | 多实体关联、需要 GraphQL/MCP |
| **关系定义** | 分散在各 Response 类中 | 集中在 ER Diagram 中 |

### 定义实体和关系

用 `base_entity()` 创建基类，在 `__relationships__` 中定义实体间关系：

```python
from pydantic import BaseModel
from typing import Annotated, Optional
from pydantic_resolve import base_entity, Relationship, config_global_resolver

BaseEntity = base_entity()

class UserEntity(BaseModel, BaseEntity):
    id: int
    name: str

class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        # Loader 可以查询 Postgres、调用 RPC、或从 Redis 获取
        # API 消费者不需要知道数据从哪来
        Relationship(fk='owner_id', target=UserEntity, name='owner', loader=user_loader)
    ]
    id: int
    name: str
    owner_id: int  # 内部 FK，可以对 API 隐藏

diagram = BaseEntity.get_diagram()
AutoLoad = diagram.create_auto_load()
config_global_resolver(diagram)
```

也可以用外部声明方式（`ErDiagram` + `Entity`），将关系定义与实体类分离。

### 使用 AutoLoad

定义好 ER Diagram 后，在 Response 模型中用 `AutoLoad()` 标注需要自动加载的字段：

```python
from pydantic_resolve import DefineSubset

class TaskResponse(TaskEntity):
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
    # AutoLoad 根据 TaskEntity 的 __relationships__ 自动生成 resolve_owner

# 使用方式与 Core API 完全一致
result = await Resolver().resolve(tasks)
```

用 `DefineSubset` 选择性暴露字段，隐藏内部 FK：

```python
class TaskResponse(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'name'))  # owner_id 被排除
    owner: Annotated[Optional[UserEntity], AutoLoad()] = None
```

### 何时使用声明式模式

**适合使用声明式模式的场景：**
- 项目中有 3 个以上互相关联的实体
- 需要生成 GraphQL schema 或 MCP 服务
- 团队需要集中管理实体关系
- 希望将 FK 字段从 API 契约中隐藏

**Core API 就足够的场景：**
- 只有少量数据加载需求
- 数据来源单一（如只用一个数据库）
- 不需要 GraphQL 或 MCP

[→ 完整 ERD 驱动指南](https://allmonday.github.io/pydantic-resolve/erd_driven/)

## 集成

### GraphQL

从 ERD 生成 GraphQL schema 并执行查询：

```python
from pydantic_resolve.graphql import GraphQLHandler

handler = GraphQLHandler(diagram)
result = await handler.execute("{ users { id name posts { title } } }")
```

[→ GraphQL 文档](./demo/graphql/README.md)

### MCP

将 GraphQL API 暴露给 AI 代理：

```python
from pydantic_resolve import AppConfig, create_mcp_server

mcp = create_mcp_server(apps=[AppConfig(name="blog", er_diagram=diagram)])
mcp.run()
```

[→ MCP 文档](https://allmonday.github.io/pydantic-resolve/api/)

### 可视化

使用 [fastapi-voyager](https://github.com/allmonday/fastapi-voyager) 进行交互式 ERD 探索：

```python
from fastapi_voyager import create_voyager

app.mount('/voyager', create_voyager(app, er_diagram=diagram))
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
