# Pydantic Resolve

> 将 Pydantic 从静态数据容器转变为强大的可组合组件

[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![PyPI Downloads](https://static.pepy.tech/badge/pydantic-resolve/month)](https://pepy.tech/projects/pydantic-resolve)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)

## 这是什么？

**pydantic-resolve** 是一个基于 Pydantic 的数据构建工具，让你可以用**声明式**的方式组装复杂的数据结构，而无需编写繁琐的命令式胶水代码。

### 它解决了什么问题？

想象一下这样的场景：你需要为前端提供 API 数据，这些数据来自多个数据源（数据库、RPC 服务等），并且需要组合、转换、计算。通常你会怎么做？

```python
# 传统方式：命令式数据组装
async def get_teams_with_detail(session):
    # 1. 获取团队列表
    teams = await session.execute(select(Team))
    teams = teams.scalars().all()

    # 2. 为每个团队获取 Sprint 列表
    for team in teams:
        team.sprints = await get_sprints_by_team(session, team.id)

        # 3. 为每个 Sprint 获取任务列表
        for sprint in team.sprints:
            sprint.tasks = await get_tasks_by_sprint(session, sprint.id)

            # 4. 为每个任务获取负责人信息
            for task in sprint.tasks:
                task.owner = await get_user_by_id(session, task.owner_id)

    # 5. 计算一些统计数据
    for team in teams:
        team.total_tasks = sum(len(sprint.tasks) for sprint in team.sprints)

    return teams
```

**问题**：
- 大量嵌套循环
- N+1 查询问题（性能差）
- 难以维护和扩展
- 数据获取逻辑与业务逻辑混杂

**pydantic-resolve 的方式**：

```python
# 声明式：描述你想要什么，而不是怎么做
class TaskResponse(BaseModel):
    id: int
    name: str
    owner_id: int

    owner: Optional[UserResponse] = None
    def resolve_owner(self, loader=Loader(user_batch_loader)):
        return loader.load(self.owner_id)

class SprintResponse(BaseModel):
    id: int
    name: str

    tasks: list[TaskResponse] = []
    def resolve_tasks(self, loader=Loader(sprint_to_tasks_loader)):
        return loader.load(self.id)

class TeamResponse(BaseModel):
    id: int
    name: str

    sprints: list[SprintResponse] = []
    def resolve_sprints(self, loader=Loader(team_to_sprints_loader)):
        return loader.load(self.id)

# 使用
teams = await query_teams_from_db(session)
result = await Resolver().resolve(teams)
```

**优势**：
- 自动批量加载（使用 DataLoader 模式）
- 无 N+1 查询问题
- 数据获取逻辑清晰分离
- 易于扩展和维护

### 核心特性

- **声明式数据组装**：通过 `resolve_{field}` 方法声明如何获取关联数据
- **自动批量加载**：内置 DataLoader，自动合并查询，避免 N+1 问题
- **数据后处理**：通过 `post_{field}` 方法在数据获取后进行转换和计算
- **跨层数据传递**：父节点可以向子节点暴露数据，子节点可以向父节点收集数据
- **实体关系图（ERD）**：定义实体关系，自动生成解析逻辑
- **框架集成**：无缝集成 FastAPI、Litestar、Django Ninja

## 快速开始

### 安装

```bash
pip install pydantic-resolve
```

> 注意：pydantic-resolve v2+ 仅支持 Pydantic v2

### 第一步：定义数据加载器

首先，你需要定义批量数据加载器（这是 Facebook DataLoader 模式的 Python 实现）：

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic_resolve import build_list

# 批量获取用户
async def batch_get_users(session: AsyncSession, user_ids: list[int]):
    result = await session.execute(select(User).where(User.id.in_(user_ids)))
    return result.scalars().all()

# 用户加载器
async def user_batch_loader(user_ids: list[int]):
    async with get_db_session() as session:
        users = await batch_get_users(session, user_ids)
        # 将用户列表映射到对应的 ID
        return build_list(users, user_ids, lambda u: u.id)

# 批量获取团队的任务
async def batch_get_tasks_by_team(session: AsyncSession, team_ids: list[int]):
    result = await session.execute(select(Task).where(Task.team_id.in_(team_ids)))
    return result.scalars().all()

# 团队任务加载器
async def team_to_tasks_loader(team_ids: list[int]):
    async with get_db_session() as session:
        tasks = await batch_get_tasks_by_team(session, team_ids)
        return build_list(tasks, team_ids, lambda t: t.team_id)
```

### 第二步：定义响应模型

使用 Pydantic BaseModel 定义响应结构，并通过 `resolve_` 前缀的方法声明如何获取关联数据：

```python
from typing import Optional, List
from pydantic import BaseModel
from pydantic_resolve import Resolver, Loader

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

class TeamResponse(BaseModel):
    id: int
    name: str

    # 声明：通过 team_id 获取该团队的所有任务
    tasks: List[TaskResponse] = []
    def resolve_tasks(self, loader=Loader(team_to_tasks_loader)):
        return loader.load(self.id)
```

### 第三步：使用 Resolver 解析数据

```python
from fastapi import FastAPI, Depends

app = FastAPI()

@app.get("/teams", response_model=List[TeamResponse])
async def get_teams():
    # 1. 从数据库获取基础数据（多个团队）
    teams_data = await get_teams_from_db()

    # 2. 转换为 Pydantic 模型
    teams = [TeamResponse.model_validate(t) for t in teams_data]

    # 3. 解析所有关联数据
    result = await Resolver().resolve(teams)

    return result
```

就这样！Resolver 会自动：
1. 发现所有 `resolve_` 方法
2. **收集所有 team 需要的 tasks ID**（比如 3 个 team，需要加载 3 次 tasks）
3. **批量调用对应的 loader**（一次查询加载所有 tasks，而不是 3 次）
4. 将结果填充到对应字段

**DataLoader 的威力**：
```python
# 假设有 3 个团队，每个团队有多个任务
# 传统方式：3 次查询
SELECT * FROM tasks WHERE team_id = 1
SELECT * FROM tasks WHERE team_id = 2
SELECT * FROM tasks WHERE team_id = 3

# DataLoader 方式：1 次查询
SELECT * FROM tasks WHERE team_id IN (1, 2, 3)
```

## 核心概念详解

### 1. DataLoader：批量加载的秘密武器

**问题**：传统的关联数据加载会导致 N+1 查询

```python
# 错误示例：N+1 查询
for task in tasks:
    task.owner = await get_user_by_id(task.owner_id)  # 产生了 N 次查询
```

**解决方案**：DataLoader 批量加载

```python
# DataLoader 会自动合并请求
tasks = [Task1(owner_id=1), Task2(owner_id=2), Task3(owner_id=1)]

# DataLoader 会将这些请求合并为一次查询：
# SELECT * FROM users WHERE id IN (1, 2)
```

### 2. resolve 方法：声明数据依赖

`resolve_{field_name}` 方法用于声明如何获取该字段的数据：

```python
class CommentResponse(BaseModel):
    id: int
    content: str
    author_id: int

    # 解析器会自动调用这个方法，并将返回值赋给 author 字段
    author: Optional[UserResponse] = None
    def resolve_author(self, loader=Loader(user_batch_loader)):
        return loader.load(self.author_id)
```

### 3. post 方法：数据后处理

当所有 `resolve_` 方法执行完成后，`post_{field_name}` 方法会被调用。这可以用于：

- 计算派生字段
- 格式化数据
- 聚合子节点的数据

```python
class SprintResponse(BaseModel):
    id: int
    name: str

    tasks: List[TaskResponse] = []
    def resolve_tasks(self, loader=Loader(sprint_to_tasks_loader)):
        return loader.load(self.id)

    # 在 tasks 加载完成后，计算总任务数
    total_tasks: int = 0
    def post_total_tasks(self):
        return len(self.tasks)

    # 计算所有任务的估算总和
    total_estimate: int = 0
    def post_total_estimate(self):
        return sum(task.estimate for task in self.tasks)
```

### 4. 跨层数据传递

**场景**：子节点需要访问父节点的数据，或者父节点需要收集子节点的数据

#### Expose：父节点向子节点暴露数据

```python
from pydantic_resolve import ExposeAs

class StoryResponse(BaseModel):
    id: int
    name: Annotated[str, ExposeAs('story_name')]  # 暴露给子节点

    tasks: List[TaskResponse] = []

class TaskResponse(BaseModel):
    id: int
    name: str

    # post/resolve 方法都可以访问祖先节点暴露的数据
    full_name: str = ""
    def post_full_name(self, ancestor_context):
        # 获取父节点（Story）的 name
        story_name = ancestor_context.get('story_name')
        return f"{story_name} - {self.name}"
```

#### Collect：子节点向父节点发送数据

```python
from pydantic_resolve import Collector, SendTo

class TaskResponse(BaseModel):
    id: int
    owner_id: int

    # 加载 owner 数据，并发送到父节点的 related_users 收集器
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
        return collector.values()
```

## 高级用法

### 使用实体关系图（ERD）

对于复杂的应用，你可以在应用级别定义实体关系，然后自动生成解析逻辑：

```python
from pydantic_resolve import base_entity, Relationship, LoadBy, config_global_resolver

# 1. 定义基础实体
BaseEntity = base_entity()

class Story(BaseModel, BaseEntity):
    __relationships__ = [
        # 定义关系：通过 id 字段加载该 story 的所有 tasks
        Relationship(field='id', target_kls=list['Task'], loader=story_to_tasks_loader),
        # 定义关系：通过 owner_id 字段加载 owner
        Relationship(field='owner_id', target_kls='User', loader=user_batch_loader),
    ]

    id: int
    name: str
    owner_id: int
    sprint_id: int

class Task(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(field='owner_id', target_kls='User', loader=user_batch_loader),
    ]

    id: int
    name: str
    owner_id: int
    story_id: int
    estimate: int

class User(BaseModel):
    id: int
    name: str
    email: str

# 2. 生成 ER 图并注册到全局 Resolver
diagram = BaseEntity.get_diagram()
config_global_resolver(diagram)

# 3. 定义响应模型时，不需要写 resolve 方法
class TaskResponse(BaseModel):
    id: int
    name: str
    owner_id: int

    # LoadBy 会自动查找 ERD 中的关系定义
    owner: Annotated[Optional[User], LoadBy('owner_id')] = None

class StoryResponse(BaseModel):
    id: int
    name: str

    tasks: Annotated[List[TaskResponse], LoadBy('id')] = []
    owner: Annotated[Optional[User], LoadBy('owner_id')] = None

# 4. 直接使用
stories = await query_stories_from_db(session)
result = await Resolver().resolve(stories)
```

优势：
- 关系定义集中管理
- 响应模型更简洁
- 类型安全
- 可视化依赖关系（配合 fastapi-voyager）

### 定义数据子集

如果你只想返回实体的部分字段，可以使用 `DefineSubset`：

```python
from pydantic_resolve import DefineSubset

# 假设有一个完整的 User 模型
class FullUser(BaseModel):
    id: int
    name: str
    email: str
    password_hash: str
    created_at: datetime
    updated_at: datetime

# 只选择需要的字段
class UserSummary(DefineSubset):
    __subset__ = (FullUser, ('id', 'name', 'email'))

# 自动生成：
# class UserSummary(BaseModel):
#     id: int
#     name: str
#     email: str
```

### 高级子集配置：SubsetConfig

如果需要更复杂的配置（比如同时暴露字段给子节点），可以使用 `SubsetConfig`：

```python
from pydantic_resolve import DefineSubset, SubsetConfig

class StoryResponse(DefineSubset):
    __subset__ = SubsetConfig(
        kls=StoryEntity,              # 源模型
        fields=['id', 'name', 'owner_id'],  # 要包含的字段
        expose_as=[('name', 'story_name')]  # 暴露给子节点的别名
        send_to=[('id', 'story_id_collector')]  # 发送给收集器
    )

# 等价于：
# class StoryResponse(BaseModel):
#     id: Annotated[int, SendTo('story_id_collector')]
#     name: Annotated[str, ExposeAs('story_name')]
#     owner_id: int
#
```

## 性能优化建议

### 1. 数据库会话管理

使用 FastAPI + SQLAlchemy 时，注意会话生命周期：

```python
@router.get("/teams", response_model=List[TeamResponse])
async def get_teams(session: AsyncSession = Depends(get_session)):
    # 1. 获取基础数据（多个团队）
    teams = await get_teams_from_db(session)

    # 2. 立即释放会话（避免死锁）
    await session.close()

    # 3. Resolver 内部的 loader 会创建新的会话
    teams = [TeamResponse.model_validate(t) for t in teams]
    result = await Resolver().resolve(teams)

    return result
```

### 2. 批量加载优化

确保你的 loader 正确实现了批量加载：

```python
# 正确：使用 IN 查询批量加载
async def user_batch_loader(user_ids: list[int]):
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users = result.scalars().all()
        return build_list(users, user_ids, lambda u: u.id)
```

**进阶：使用 `_query_meta` 优化查询字段**

DataLoader 可以通过 `self._query_meta` 获取需要的字段信息，只查询必要的数据：

```python
from aiodataloader import DataLoader

class UserLoader(DataLoader):
    async def batch_load_fn(self, user_ids: list[int]):
        # 获取响应模型需要的字段
        required_fields = self._query_meta.get('fields', ['*'])

        # 只查询需要的字段（优化 SQL 查询）
        async with get_session() as session:
            # 如果指定了字段，只查询这些字段
            if required_fields != ['*']:
                columns = [getattr(User, f) for f in required_fields]
                result = await session.execute(
                    select(*columns).where(User.id.in_(user_ids))
                )
            else:
                result = await session.execute(
                    select(User).where(User.id.in_(user_ids))
                )

            users = result.scalars().all()
            return build_list(users, user_ids, lambda u: u.id)
```

**优势**：
- 如果 `UserResponse` 只需要 `id` 和 `name`，SQL 只会查询这两个字段
- 减少数据传输量和内存占用
- 提升查询性能，特别是对于包含大量字段的表

**注意**：`self._query_meta` 在 Resolver 第一次扫描后才会被填充。

## 实战案例

### 场景：项目管理系统

需求：获取一个团队的所有 Sprint，包含：
- 每个 Sprint 的所有 Story
- 每个 Story 的所有 Task
- 每个 Task 的负责人
- 每层的统计数据（总任务数、总估算等）

```python
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from pydantic_resolve import (
    Resolver, Loader, LoadBy,
    ExposeAs, Collector, SendTo,
    base_entity, Relationship, config_global_resolver,
    build_list, DefineSubset, SubsetConfig
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# 0. 定义数据加载器
async def user_batch_loader(user_ids: list[int]):
    """批量加载用户"""
    async with get_db_session() as session:
        result = await session.execute(select(User).where(User.id.in_(user_ids)))
        users = result.scalars().all()
        return build_list(users, user_ids, lambda u: u.id)

async def story_to_tasks_loader(story_ids: list[int]):
    """批量加载 Story 的 Tasks"""
    async with get_db_session() as session:
        result = await session.execute(select(Task).where(Task.story_id.in_(story_ids)))
        tasks = result.scalars().all()
        return build_list(tasks, story_ids, lambda t: t.story_id)

async def sprint_to_stories_loader(sprint_ids: list[int]):
    """批量加载 Sprint 的 Stories"""
    async with get_db_session() as session:
        result = await session.execute(select(Story).where(Story.sprint_id.in_(sprint_ids)))
        stories = result.scalars().all()
        return build_list(stories, sprint_ids, lambda s: s.sprint_id)

# 1. 定义实体和 ERD
BaseEntity = base_entity()

class UserEntity(BaseModel):
    """用户实体"""
    id: int
    name: str
    email: str

class TaskEntity(BaseModel, BaseEntity):
    """任务实体"""
    __relationships__ = [
        Relationship(field='owner_id', target_kls=UserEntity, loader=user_batch_loader)
    ]
    id: int
    name: str
    owner_id: int
    story_id: int
    estimate: int

class StoryEntity(BaseModel, BaseEntity):
    """故事实体"""
    __relationships__ = [
        Relationship(field='id', target_kls=list[TaskEntity], loader=story_to_tasks_loader),
        Relationship(field='owner_id', target_kls=UserEntity, loader=user_batch_loader)
    ]
    id: int
    name: str
    owner_id: int
    sprint_id: int

class SprintEntity(BaseModel, BaseEntity):
    """Sprint 实体"""
    __relationships__ = [
        Relationship(field='id', target_kls=list[StoryEntity], loader=sprint_to_stories_loader)
    ]
    id: int
    name: str
    team_id: int

# 注册 ERD
config_global_resolver(BaseEntity.get_diagram())

# 2. 定义响应模型（使用 DefineSubset 从实体中选择字段）

# 基础用户响应
class UserResponse(DefineSubset):
    __subset__ = (UserEntity, ('id', 'name'))

# 场景1：基础数据组装 - 使用 LoadBy 自动解析关联数据
class TaskResponse(DefineSubset):
    __subset__ = SubsetConfig(
        kls=TaskEntity,
        fields=['id', 'name', 'estimate', 'owner_id']
    )

    # LoadBy 会自动根据 ERD 中的 Relationship 定义解析 owner
    owner: Annotated[Optional[UserResponse], LoadBy('owner_id')] = None

# 场景2：父节点向子节点暴露数据 - Task 名称需要添加 Story 前缀
class TaskResponseWithPrefix(DefineSubset):
    __subset__ = SubsetConfig(
        kls=TaskEntity,
        fields=['id', 'name', 'estimate', 'owner_id']
    )

    owner: Annotated[Optional[UserResponse], LoadBy('owner_id')] = None

    # post 方法可以访问祖先节点暴露的数据
    full_name: str = ""
    def post_full_name(self, ancestor_context):
        # 获取父节点（Story）暴露的 story_name
        story_name = ancestor_context.get('story_name')
        return f"{story_name} - {self.name}"

# 场景3：计算额外字段 - Story 需要计算所有 Task 的总估算
class StoryResponse(DefineSubset):
    __subset__ = SubsetConfig(
        kls=StoryEntity,
        fields=['id', 'name', 'owner_id'],
        expose_as=[('name', 'story_name')]  # 暴露给子节点（场景2使用）
    )

    # LoadBy 会自动根据 ERD 中的 Relationship 定义解析 tasks
    tasks: Annotated[List[TaskResponse], LoadBy('id')] = []

    # post_ 方法在所有 resolve_ 方法完成后执行
    total_estimate: int = 0
    def post_total_estimate(self):
        return sum(t.estimate for t in self.tasks)

# 场景4：父节点从子节点收集数据 - Story 需要收集所有涉及的开发者
class TaskResponseForCollect(DefineSubset):
    __subset__ = SubsetConfig(
        kls=TaskEntity,
        fields=['id', 'name', 'estimate', 'owner_id'],
    )

    owner: Annotated[Optional[UserResponse], LoadBy('owner_id'), SendTo('related_users')] = None

class StoryResponseWithCollect(DefineSubset):
    __subset__ = (StoryEntity, ('id', 'name', 'owner_id'))

    tasks: Annotated[List[TaskResponseForCollect], LoadBy('id')] = []

    # 收集所有子节点的 owner
    related_users: List[UserResponse] = []
    def post_related_users(self, collector=Collector(alias='related_users')):
        return collector.values()

# Sprint 响应模型 - 综合使用以上特性
class SprintResponse(DefineSubset):
    __subset__ = (SprintEntity, ('id', 'name'))

    # 使用 LoadBy 自动解析 stories
    stories: Annotated[List[StoryResponse], LoadBy('id')] = []

    # 计算统计数据（所有 story 的总估算）
    total_estimate: int = 0
    def post_total_estimate(self):
        return sum(s.total_estimate for s in self.stories)

# 3. API 端点
@app.get("/sprints", response_model=List[SprintResponse])
async def get_sprints(session: AsyncSession = Depends(get_session)):
    """获取所有 Sprint，包含完整的层级数据"""
    sprints_data = await get_sprints_from_db(session)
    await session.close()

    sprints = [SprintResponse.model_validate(s) for s in sprints_data]
    result = await Resolver().resolve(sprints)

    return result
```

**架构优势**：
- **实体和响应分离**：Entity 定义业务实体和关系，Response 定义 API 返回结构
- **复用关系定义**：通过 ERD 一次性定义关系，所有响应模型都可以使用 `LoadBy` 自动解析
- **类型安全**：DefineSubset 确保字段类型从实体继承
- **灵活组合**：可以基于同一组实体定义不同的响应模型，并且可以复用 DataLoader
- **查询优化**：DataLoader 可通过 `self._query_meta` 获取需要的字段信息，只查询必要的数据（如 SQL `SELECT` 只选择需要的列）

**场景覆盖**：
- **场景1**：基础数据组装 - 自动解析关联数据
- **场景2**：Expose - 父节点向子节点暴露数据（如 Task 使用 Story 的名称）
- **场景3**：post - 计算额外字段（如计算总估算）
- **场景4**：Collect - 父节点从子节点收集数据（如收集所有开发者）

每个场景都是独立的、可复用的，可以根据实际需求组合使用。


## 可视化依赖关系

安装 [fastapi-voyager](https://github.com/allmonday/fastapi-voyager) 可以可视化 Pydantic 模型的依赖关系：

```bash
pip install fastapi-voyager
```

配置后即可访问 `/voyager` 路径看到依赖关系图。

## 为什么不用 GraphQL？

虽然 pydantic-resolve 的灵感来自 GraphQL，但它更适合作为 BFF（Backend For Frontend）层的解决方案：

| 特性 | GraphQL | pydantic-resolve |
|------|---------|------------------|
| 性能 | 需要复杂的 DataLoader 配置 | 内置批量加载 |
| 类型安全 | 需要额外的工具链 | 原生 Pydantic 类型支持 |
| 学习曲线 | 陡峭（Schema、Resolver、Loader...） | 平缓（只需要 Pydantic） |
| 调试 | 困难 | 简单（标准的 Python 代码） |
| 集成 | 需要额外的服务器 | 无缝集成现有框架 |
| 灵活性 | 查询过于灵活，难以优化 | 明确的 API 契约 |


## 更多资源

- **完整文档**: https://allmonday.github.io/pydantic-resolve/
- **示例项目**: https://github.com/allmonday/composition-oriented-development-pattern
- **在线演示**: https://www.newsyeah.fun/voyager/?tag=sample_1
- **API 参考**: https://allmonday.github.io/pydantic-resolve/api/

## 开发

```bash
# 克隆仓库
git clone https://github.com/allmonday/pydantic_resolve.git
cd pydantic_resolve

# 安装开发依赖
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# 运行测试
uv run pytest tests/

# 查看测试覆盖率
tox -e coverage
```

## 许可证

MIT License

## 作者

tangkikodo (allmonday@126.com)
