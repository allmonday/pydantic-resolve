# FastAPI 中 Pydantic 的正确使用方式：Entity-First 架构

## 一、引言：被忽视的架构问题

### 1.1 现状观察

FastAPI 已经成为 Python Web 开发的首选框架之一，其与 Pydantic 的深度集成让数据验证变得前所未有的简单。然而，在浏览大量的 FastAPI 项目、官方模板、社区教程和最佳实践指南后，我们发现了一个惊人的相似性：几乎所有的项目都遵循着相同的模式——先定义 SQLAlchemy ORM 模型，然后基于这些模型创建 Pydantic schema。

这种"ORM 先行、Pydantic 跟随"的模式已经如此普遍，以至于许多开发者从未质疑过它的合理性。官方的 full-stack 模板采用这种方式，获得数千颗星的社区最佳实践仓库也推荐这种方式，大量的教程和文章都在传授这种方式。但这并不意味着它是正确的。

当我们深入分析这种模式的实际应用时，一些深层的问题开始浮现。Pydantic schema 被动地复制 ORM 模型的字段定义，导致类型定义在两个地方重复；数据库设计的任何变更都会直接影响到 API 契约；业务概念被数据库结构深度渗透，难以表达领域模型的真实语义；当需要从多个数据源（数据库、RPC、缓存等）组合数据时，代码变得异常复杂且难以维护。

这些问题的根源在于我们混淆了两个不同层次的抽象：数据库模型（ORM）和领域模型（Entity）。ORM 模型应该只是数据持久化的实现细节，而不应该成为整个架构的中心。Pydantic schema 也不应该成为 ORM 的影子，而应该成为表达业务概念和 API 契约的独立抽象层。

### 1.2 核心论点

本文的核心论点很简单：Pydantic schema 不应该是 ORM 的影子，而应该建立在独立的业务实体层之上。这不仅仅是一个代码组织的问题，而是一个关乎架构清晰度、可维护性和长期演进的系统性问题。

**领域模型是架构的核心**。业务实体（Entity）应该表达纯粹的领域概念，比如"用户"、"任务"、"项目"，而不是数据库表。这些实体定义了业务对象的结构和它们之间的关系，独立于任何技术实现。当我们谈论业务时，我们说的是"这个任务属于哪个用户"、"这个项目包含哪些任务"，而不是"tasks 表有 user_id 外键"。领域模型的存在让我们能够用业务语言来思考和设计系统，而不是被技术实现细节束缚。

**具体用例驱动 API 设计**。每个 API 端点都是为特定的业务场景服务的，比如"用户列表页面需要用户的 id 和 name"、"任务详情页面需要任务的完整信息和负责人的详细信息"。这些用例决定了 API 应该返回什么数据，而不是数据库有什么字段。Pydantic schema 应该根据具体用例来定义，从领域模型中选择需要的字段，添加用例特有的计算字段和验证逻辑。这才是"响应模型"（Response Model）的真正含义。

**数据层只是实现细节**。无论数据存储在 PostgreSQL、MySQL、MongoDB 这样的数据库中，还是从 Redis、Memcached 这样的缓存中读取，亦或是通过 gRPC、REST API 从外部服务获取，这些都不应该影响领域模型和 API 契约的定义。数据层负责高效、可靠地获取数据，但它只是一个可替换的实现细节。数据库结构可能会改变，外部服务可能会迁移，缓存策略可能会调整，但只要数据层能够提供领域模型需要的数据，这些变化就不应该波及到业务逻辑和 API 契约。

这种分层架构的核心价值在于**稳定性和可演进性**。领域模型作为稳定的内核，独立于具体实现而存在。API 契约根据用例设计，为前端提供稳定的接口。数据层作为可替换的外壳，可以根据性能需求、技术栈升级、业务变化而灵活调整。当这三个层次清晰分离时，系统就具备了持续演进的能力——我们可以在不影响业务逻辑的前提下优化数据访问策略，可以在不破坏 API 契约的前提下重构数据模型，可以在不改变领域模型的前提下调整 API 设计。

这不仅是理论上的优雅，也是实践中的必要。当项目规模增长、业务复杂度提升、团队协作需求增加时，清晰的分层架构会成为项目能否持续演进的关键因素。一个被数据库结构深度渗透的系统，每一次数据库变更都会牵一发而动全身；而一个建立在稳定领域模型基础上的系统，则可以更从容地应对变化。

## 二、"ORM 先行"的架构陷阱

### 2.1 典型的项目结构

在大多数 FastAPI 项目中，你会看到相似的组织方式：

```
project/
├── models/
│   ├── user.py          # ORM 模型（数据库表结构）
│   ├── task.py
│   └── ...
├── schemas/
│   ├── user.py          # Pydantic schema（从 ORM 复制字段）
│   ├── task.py
│   └── ...
├── routes/
│   └── ...
└── services/
    └── ...
```

这种结构看起来很合理——数据模型和 API 契约分开存放——但问题在于，Pydantic schema 往往只是对数据库模型的被动复制，字段名称、类型、甚至注释都几乎一模一样。更深层的问题在于，整个项目的数据流向是单向的：从数据库模型到 Pydantic schema，没有任何独立的业务概念层存在。

### 2.2 核心问题分析

#### 问题 1：Schema 被动跟随 ORM

当一个项目的 Pydantic schema 只是数据库模型的影子时，就会出现一系列深层问题。最明显的是类型定义的重复：同样的字段名、同样的类型约束，在两个不同的地方定义并维护。这种重复违反了软件开发中的 DRY（Don't Repeat Yourself）原则，但更严重的是它暴露了架构本质上的混乱——API 契约不应该受限于数据库的物理设计。

试想一个实际场景：数据库中存储用户密码哈希是为了认证需求，这个字段是数据库实现细节，API 响应中完全不应该包含它。但由于 Pydantic schema 是从数据库模型复制的，开发者往往不加思考地将这个字段也包含进来，造成安全隐患。更常见的情况是，当数据库团队决定优化表结构（比如将一个大表拆分成多个小表，或者调整字段类型以优化性能），这些纯粹的技术决策会直接波及到 API 契约，导致前端应用也需要相应修改。这违反了一个基本原则：API 应该是稳定的对外契约，而数据库实现是可以优化的内部细节。

#### 问题 2：业务概念被数据库结构渗透

当数据库结构成为整个架构的中心时，业务概念也会被数据库的设计细节所束缚。一个典型的例子是任务管理系统中"负责人"和"报告人"的概念。

**业务视角**：从业务角度看，这是两个清晰的角色——任务有一个负责人，也有一个报告人。这是业务领域中的自然概念。

**数据库设计决策**：在数据库设计中，这可能通过多种方式实现：两个外键字段（`owner_id` 和 `reporter_id`）、单个 `user_id` 加上 `role` 字段、或者多对多关系表。这些是纯粹的技术决策，取决于性能需求、数据量、查询模式等因素。

当 API 直接暴露数据库结构时，业务概念就被技术细节取代了：

```python
# 数据库设计 1：使用两个外键
class TaskORM(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    title = Column(String(100))
    owner_id = Column(Integer, ForeignKey('users.id'))      # 负责人
    reporter_id = Column(Integer, ForeignKey('users.id'))   # 报告人

# API Schema 被动复制 DB 结构
class TaskResponse(BaseModel):
    id: int
    title: str
    owner_id: int          # 前端必须理解这是什么
    reporter_id: int       # 前端必须理解这是什么
    owner: Optional['UserResponse']
    reporter: Optional['UserResponse']
```

现在的问题是：前端开发者需要理解 `owner_id` 和 `reporter_id` 的区别，需要知道为什么有两个字段。这些是数据库设计细节，与业务概念无关。如果后续数据库团队决定重构表结构（比如为了性能将两个字段合并为一个字段），API 也要跟着改，前端代码也需要相应调整。

```python
# 数据库设计 2：重构为单个字段 + role
class TaskORM(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    title = Column(String(100))
    user_id = Column(Integer, ForeignKey('users.id'))   # 合并字段
    role = Column(String(20))  # 'owner' 或 'reporter'

# API Schema 必须跟着改变
class TaskResponse(BaseModel):
    id: int
    title: str
    user_id: int           # 现在改成了 user_id
    role: str              # 新增了 role 字段
    # 前端代码必须全部修改！
```

这种变化与业务无关——业务上仍然有"负责人"和"报告人"两个角色——但纯粹的技术决策（数据库重构）却影响了系统的各个层次，包括前端应用。这正是业务概念被数据库结构渗透的直接后果。

真正的业务概念——"这个任务属于谁"、"谁负责跟进这个任务"——被淹没在了外键关系和表结构的技术细节中。我们无法用业务语言来思考和设计 API，而必须时刻考虑数据库是如何存储这些数据的。这种概念的混淆使得代码难以理解和维护，新加入的团队成员需要先理解数据库设计才能理解业务逻辑。

#### 问题 3：无法使用关系映射时的数据组装困境

SQLAlchemy 提供了 `relationship` 功能，可以在查询时自动加载关联数据，看起来很方便。但在实际项目中，这个功能并非万能。跨数据库查询时它无能为力，复杂的 JOIN 条件下它难以使用，需要优化性能的只读查询或报表查询往往也不适合用它。一旦脱离了 `relationship` 的便利，开发者就必须手动编写冗长的数据组装代码。

这个过程通常包含多个重复的步骤：先查询主数据（比如文章列表），然后收集所有的关联 ID（比如所有文章的作者 ID），接着批量查询关联数据（比如根据 ID 列表查询用户），再手动构建 ID 到对象的映射字典，最后循环遍历主数据，手动查找对应的关联对象并组装成最终的响应结构。这个过程代码量大、容易出错，而且每次需要类似的关联查询时都要重复编写。

更危险的是，手动编写这些代码很容易产生性能问题。如果开发者忘记批量查询，而是在循环中逐个查询关联数据，就会立即陷入经典的 N+1 查询陷阱——原本一次批量查询就能解决的问题，变成了 N 次独立查询。当数据量增大时，性能问题会迅速暴露。而使用 `relationship` 虽然能避免这个问题，但它又回到了之前提到的困境：不是所有场景都适合用它。

这种数据组装逻辑散落在项目的各个地方，每个需要关联数据的 API 端点都可能有一段类似的代码。这不仅违反了单一职责原则，也使得代码难以复用和测试。当需要优化数据加载策略时（比如添加缓存、调整查询顺序），需要在多处修改，容易遗漏或产生不一致。

#### 问题 4：多数据源难以统一处理

现代应用的复杂性在于数据往往不只来自一个地方。用户信息可能在 PostgreSQL 数据库中，订单数据可能在 MongoDB 中，库存状态可能需要调用外部 RPC 服务获取，推荐列表可能从 Redis 缓存中读取。当这些数据需要组合成一个统一的 API 响应时，传统的方式就显露出明显的不足。

每个数据源都有自己的数据格式和访问方式。数据库返回 ORM 对象，RPC 服务返回字典或自定义对象，缓存返回序列化的字符串或字节流。为了将它们统一到 Pydantic schema 中，开发者需要编写各种转换函数，处理字段映射、类型转换、数据提取等细节。这些转换逻辑分散在各个地方，难以集中管理和优化。

更糟糕的是，当某个数据源需要迁移或升级时（比如将用户服务从数据库迁移到独立的微服务），所有涉及该数据源的转换代码都需要修改。由于这些转换逻辑与业务逻辑混杂在一起，修改的影响范围难以评估，测试成本也很高。缺少统一的抽象层使得系统难以应对数据源的变化，每次变化都可能牵一发而动全身。

#### 问题 5：Schema 难以复用和组合

在实际项目中，同一个实体往往需要在不同的场景下以不同的形式出现。用户列表页面可能只需要显示用户的 ID 和姓名，用户详情页面需要显示完整信息包括邮箱、手机号、注册时间等，任务列表中嵌入的用户信息可能只需要 ID 和头像 URL。如果为每个场景都单独定义一个 Pydantic schema，就会出现大量的重复定义，字段类型的修改需要同步多处。

传统做法中，开发者要么复制粘贴代码（违反 DRY 原则），要么尝试用继承来组合（但 Pydantic 的继承机制并不直观，容易产生混淆）。更深层的问题是，这些 schema 之间缺少明确的"属于同一个实体"的关系——从代码上看，`UserSummary`、`UserDetail`、`UserIdOnly` 是三个独立的类，无法直观地看出它们都是对"用户"这个业务实体的不同视图。

这种缺乏统一性的schema定义，使得代码难以维护。当实体的字段类型需要修改时（比如将用户 ID 从整数改为 UUID），需要搜索所有相关的 schema 定义并逐一修改，很容易遗漏。也没有类型系统能保证这些 schema 的一致性——编译器不会告诉你 `UserSummary` 和 `UserDetail` 中的 `id` 字段类型不同。

## 三、Entity-First 架构

### 3.1 核心理念
```
┌─────────────────────────────────────┐
│   API Layer (Response)              │  ← API 契约，对外暴露
│   - 从 Entity 选择字段               │
│   - 定义 API 特有的计算字段          │
├─────────────────────────────────────┤
│   Domain Layer (Entity)             │  ← 业务概念，关系定义
│   - 定义业务实体                     │
│   - 定义实体关系（ERD）              │
│   - 独立于具体实现                   │
├─────────────────────────────────────┤
│   Data Layer (Repository)           │  ← 数据获取，封装持久化细节
│   - ORM / RPC / Cache / HTTP API    │
│   - 通过 Repository 统一接口         │
└─────────────────────────────────────┘
```

**Repository 模式**是数据层的核心抽象。它封装了所有的持久化细节——无论是使用 ORM 查询数据库、调用 RPC 服务、读取缓存，还是访问外部 API——统一暴露为简单的方法接口（如 `get_by_id`、`get_by_ids`、`find_all`）。领域层（Entity）通过 Repository 获取数据，而不需要关心数据具体来自哪里或如何加载。

### 3.2 优势与挑战

#### Entity-First 的核心优势

**稳定性和可演进性**是 Entity-First 架构最显著的优势。通过建立独立的业务实体层，系统获得了一个稳定的内核。当数据库结构需要优化时（比如拆分大表、调整索引、迁移到新数据库），只需要修改数据层的 Repository 实现，领域模型和 API 契约完全不受影响。当业务需求变化导致 API 契约需要调整时，只需要修改 Response 定义，数据层和领域模型保持不变。当业务逻辑演进需要新的实体关系时，只需要更新 ERD 定义，已有的数据访问逻辑可以保持稳定。这种三层分离使得系统具备了真正的持续演进能力。

**业务语义清晰**是另一个重要优势。在 Entity-First 架构中，我们用业务语言来定义系统，而不是数据库术语。`TaskEntity` 拥有 `owner` 和 `reporter` 这样的业务关系，而不是暴露 `owner_id` 和 `reporter_id` 这样的数据库外键。前端开发者不需要理解数据库设计，只需要理解业务概念。新加入的团队成员可以通过阅读 Entity 定义快速理解业务模型，而不需要先研究复杂的表结构和外键关系。

**多数据源的统一抽象**让复杂系统的开发变得简单。用户信息可能来自 PostgreSQL，订单数据可能来自 MongoDB，推荐列表可能从 Redis 缓存读取，库存状态可能通过 RPC 调用获取。在 Entity-First 架构中，这些差异都被数据访问层屏蔽了。Entity 只需要声明"我需要什么数据"，而不需要关心"数据从哪里来"。当某个数据源需要迁移或升级时（比如将用户服务从数据库迁移到微服务），只需要修改对应的 Repository，Entity 和 Response 完全不需要改动。

#### 核心挑战：数据关联与业务组合的鸿沟

**问题 1：Repository 的职责边界模糊**

Entity-First 架构引入了独立的业务实体层和 Repository 模式，这确实解决了很多问题。但在实际开发中，一个根本性的问题很快浮现：Repository 应该负责什么？

最直观的理解是，Repository 负责数据访问——`get_by_id`、`find_all`、`batch_get` 这样的方法。当 API 需要返回一个包含关联数据的响应时，比如"任务列表需要包含负责人信息"，问题就出现了：这个组装逻辑应该放在哪里？

**选项 1：放在 Repository 中**
```python
class TaskRepository:
    async def get_tasks_with_owners(self):
        # Repository 负责加载关联数据
        tasks = await self.get_tasks()
        user_ids = [t.owner_id for t in tasks]
        users = await user_repo.get_by_ids(user_ids)
        # 手动组装...
        return tasks_with_owners
```
问题：Repository 变得臃肿，职责混杂。每个不同的用例都需要一个特定的方法——`get_tasks_with_owners`、`get_tasks_with_projects`、`get_tasks_with_owners_and_projects`……Repository 成了用例的堆砌场。

**选项 2：放在 Service 层中**
```python
class TaskService:
    async def get_task_list_with_users(self):
        # Service 负责组装数据
        tasks = await task_repo.get_tasks()
        users = await user_repo.get_by_ids([t.owner_id for t in tasks])
        # 手动组装...
        return assembled_tasks
```
问题：Service 层充斥着数据组装代码。这些代码重复、易错、难以维护，而且与业务逻辑混杂在一起。

无论选择哪种方式，核心问题都存在：**数据组装逻辑没有合适的地方安放**。Repository 应该只负责数据访问，Service 应该只负责业务逻辑，Response 应该只负责数据结构定义。但在 Entity-First 架构中，当需要从多个 Repository 获取数据并组合成响应时，这个逻辑应该放在哪里？传统的三层架构没有给出明确的答案。

---

**总结：Entity-First 架构的缺失拼图**

Entity-First 架构提供了一个清晰的理论框架——独立的业务实体层、Repository 模式、从 Entity 派生 Response。但在实际落地时，它缺少一个关键的执行层来处理**数据组装逻辑**：当需要从多个 Repository 获取数据并组合成响应时，这个逻辑应该放在哪里？

这个问题不解决，Entity-First 架构在实践中就会遇到两难选择：
- 让 Repository 承担数据组装职责 → Repository 变得臃肿，成为用例的堆砌场
- 让 Service 承担数据组装职责 → Service 层充斥着重复、易错的数据组装代码
- 让 Response 承担数据组装职责 → 每个 Response 都要自己实现，批量加载、N+1 查询、错误处理等问题都需要手动解决

这正是 pydantic-resolve 试图解决的问题——它提供了 Entity-First 架构中缺失的数据组装执行层。

### 3.3 实现方式

#### Step 1: 定义业务实体（Entity）
```python
from pydantic import BaseModel
from pydantic_resolve import base_entity, Relationship

# 1. 创建 Entity 基类
BaseEntity = base_entity()

# 2. 定义业务实体（不依赖 ORM）
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
            loader=user_loader  # 不关心从哪加载
        )
    ]
    id: int
    name: str
    owner_id: int
    estimate: int
```

**关键点**：
- Entity 是业务概念，不绑定具体实现
- 关系通过 loader 连接，而不是 DB 外键
- 可以表达跨数据源的关系

#### Step 2: 定义数据加载器（Loader）
```python
# Loader 可以连接任意数据源
async def user_loader(user_ids: list[int]):
    # 从 ORM 加载
    users = await UserORM.filter(UserORM.id.in_(user_ids))
    return build_list(users, user_ids, lambda u: u.id)

# 或者从 RPC 加载
async def user_loader_from_rpc(user_ids: list[int]):
    users = await user_rpc.batch_get_users(user_ids)
    return build_list(users, user_ids, lambda u: u['id'])

# 或者从 Redis 加载
async def user_loader_from_cache(user_ids: list[int]):
    users = await redis.mget(f"user:{uid}" for uid in user_ids)
    return build_list(users, user_ids, lambda u: u['id'])
```

**关键点**：
- Loader 屏蔽数据源差异
- Entity 不关心数据从哪来
- 可以轻松切换或组合数据源

#### Step 3: 从 Entity 定义 API Response
```python
from pydantic_resolve import DefineSubset, LoadBy, SubsetConfig

# 场景 1：用户摘要
class UserSummary(DefineSubset):
    __subset__ = (UserEntity, ('id', 'name'))

# 场景 2：任务列表（包含负责人）
class TaskResponse(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'name', 'estimate'))

    # 自动解析 owner，无需写 resolve 方法
    owner: Annotated[Optional[UserSummary], LoadBy('owner_id')] = None

# 场景 3：任务详情（包含更多字段）
class TaskDetailResponse(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'name', 'estimate', 'created_at'))

    owner: Annotated[Optional[UserDetail], LoadBy('owner_id')] = None
```

**关键点**：
- Response 从 Entity 派生，类型安全
- 自动继承 Entity 的关系定义
- 可以复用和组合不同的字段子集
- Entity 变更时，Response 自动同步

### 3.3 架构优势

#### 优势 1：清晰的分层
- **Entity** → 领域层，表达业务概念
- **Response** → API 层，定义对外契约
- **Loader** → 数据层，处理实现细节

#### 优势 2：独立演进
- DB 结构改变 → 只需修改 Loader
- API 契约改变 → 只需修改 Response
- 业务逻辑改变 → 修改 Entity 和关系

#### 优势 3：统一的类型系统
```python
# Entity 作为"单一真相来源"
# 所有 Response 都从它派生，确保类型一致

class UserSummary(DefineSubset):
    __subset__ = (UserEntity, ('id', 'name'))

class UserDetail(DefineSubset):
    __subset__ = (UserEntity, ('id', 'name', 'email'))

# 类型安全：id 字段在所有 Response 中都是 int
```

#### 优势 4：天然支持多数据源
```python
# 可以轻松组合不同数据源的关系
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(
            field='owner_id',
            target_kls=UserEntity,
            loader=user_from_db_loader  # 从 DB 加载
        ),
        Relationship(
            field='project_id',
            target_kls=ProjectEntity,
            loader=project_from_rpc_loader  # 从 RPC 加载
        ),
        Relationship(
            field='status_id',
            target_kls=StatusEntity,
            loader=status_from_cache_loader  # 从缓存加载
        ),
    ]
```

#### 优势 5：自动数据组装，告别冗长代码

**对比：传统方式 vs pydantic-resolve**

**传统方式**（5个步骤，~30行代码）：
```python
async def get_posts_with_users(session: AsyncSession):
    # 1. 查询 posts
    posts_result = await session.execute(select(Post))
    posts = posts_result.scalars().all()

    # 2. 收集所有 user_id
    user_ids = list(set([post.user_id for post in posts]))

    # 3. 批量查询 users
    users_result = await session.execute(
        select(User).where(User.id.in_(user_ids))
    )
    users = users_result.scalars().all()

    # 4. 构建 user_id -> user 的映射
    user_map = {user.id: user for user in users}

    # 5. 手动组装 response
    result = []
    for post in posts:
        post_data = PostResponse(
            id=post.id,
            title=post.title,
            user_id=post.user_id
        )
        if post.user_id in user_map:
            user = user_map[post.user_id]
            post_data.user = UserResponse(
                id=user.id,
                name=user.name,
                email=user.email
            )
        result.append(post_data)

    return result
```

**pydantic-resolve 方式**（声明式，~10行代码）：
```python
# 1. 定义 Loader
async def user_batch_loader(user_ids: list[int]):
    async with get_db_session() as session:
        result = await session.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users = result.scalars().all()
        return build_list(users, user_ids, lambda u: u.id)

# 2. 定义 Response（声明如何获取关联数据）
class PostResponse(BaseModel):
    id: int
    title: str
    user_id: int

    user: Optional[UserResponse] = None
    def resolve_user(self, loader=Loader(user_batch_loader)):
        return loader.load(self.user_id)

# 3. 使用 Resolver 自动组装
@router.get("/posts", response_model=List[PostResponse])
async def get_posts():
    posts = await query_posts_from_db()
    return await Resolver().resolve(posts)
```

**对比结果**：
| 维度 | 传统方式 | pydantic-resolve |
|------|----------|------------------|
| 代码行数 | ~30 行 | ~10 行 |
| 是否手动批量 | ✗ 需要手动实现 | ✓ 自动批量 |
| 是否容易出错 | ✗ 手动构建映射 | ✓ 框架保证 |
| 是否可复用 | ✗ 每处重复写 | ✓ Loader 可复用 |
| N+1 风险 | ✗ 容易忘记批量 | ✓ 自动避免 |
| 职责分离 | ✗ 数据组装散落各处 | ✓ 清晰分层 |

**关键差异**：
- **传统方式**：命令式，关注"怎么做"（如何查询、如何映射、如何组装）
- **pydantic-resolve**：声明式，关注"要什么"（需要哪些关联数据）

**更复杂的场景**：

当有多层嵌套时，传统方式的代码复杂度会指数增长：

```python
# 传统方式：获取 Sprints → Stories → Tasks → Owners（4层嵌套）
async def get_sprints_with_full_detail(session):
    # 需要 4 层循环，每个循环都要：
    # 1. 查询当前层数据
    # 2. 收集下一层的 ID
    # 3. 批量查询下一层数据
    # 4. 构建映射
    # 5. 手动组装
    # 代码会超过 100 行，难以维护
```

```python
# pydantic-resolve：同样的需求
class SprintResponse(BaseModel):
    id: int
    name: str

    stories: List[StoryResponse] = []
    def resolve_stories(self, loader=Loader(stprint_to_stories_loader)):
        return loader.load(self.id)

class StoryResponse(BaseModel):
    id: int
    name: str

    tasks: List[TaskResponse] = []
    def resolve_tasks(self, loader=Loader(story_to_tasks_loader)):
        return loader.load(self.id)

class TaskResponse(BaseModel):
    id: int
    name: str
    owner_id: int

    owner: Optional[UserResponse] = None
    def resolve_owner(self, loader=Loader(user_loader)):
        return loader.load(self.owner_id)

# 使用
sprints = await query_sprints_from_db()
result = await Resolver().resolve(sprints)
```

**代码量对比**：
- 传统方式：100+ 行，难以维护
- pydantic-resolve：30 行，清晰易读

## 四、实战案例：重构现有项目

### 4.1 重构前（ORM-First）
```python
# models/task.py（ORM）
class TaskORM(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    owner_id = Column(Integer, ForeignKey('users.id'))
    project_id = Column(Integer, ForeignKey('projects.id'))

# schemas/task.py（从 ORM 复制）
class TaskBase(BaseModel):
    name: str

class TaskCreate(TaskBase):
    owner_id: int
    project_id: int

class TaskResponse(TaskBase):
    id: int
    owner_id: int
    project_id: int
    owner: Optional['UserResponse']
    project: Optional['ProjectResponse']

    def resolve_owner(self, loader=Loader(user_loader)):
        return loader.load(self.owner_id)

    def resolve_project(self, loader=Loader(project_loader)):
        return loader.load(self.project_id)

# routes/task.py
@router.get("/tasks", response_model=List[TaskResponse])
async def get_tasks(session: AsyncSession = Depends(get_session)):
    tasks = await session.execute(select(TaskORM))
    return [TaskResponse.model_validate(t) for t in tasks.scalars()]
```

### 4.2 重构后（Entity-First）
```python
# entities/task.py（业务实体）
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(field='owner_id', target_kls=UserEntity, loader=user_loader),
        Relationship(field='project_id', target_kls=ProjectEntity, loader=project_loader),
    ]
    id: int
    name: str
    owner_id: int
    project_id: int

# responses/task.py（API 契约）
class TaskResponse(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'name', 'owner_id', 'project_id'))

    owner: Annotated[Optional[UserResponse], LoadBy('owner_id')] = None
    project: Annotated[Optional[ProjectSummary], LoadBy('project_id')] = None

# routes/task.py（保持不变）
@router.get("/tasks", response_model=List[TaskResponse])
async def get_tasks():
    tasks = await query_tasks_from_db()
    return await Resolver().resolve(tasks)
```

### 4.3 对比分析

| 维度 | ORM-First | Entity-First |
|------|-----------|--------------|
| 类型定义分散 | ORM 和 Schema 重复定义 | Entity 作为单一来源 |
| 关系定义 | 每个 Response 重复写 resolve | ERD 统一定义，自动复用 |
| 数据源切换 | 需要修改多处 | 只需修改 Loader |
| 字段子集 | 手动复制粘贴 | DefineSubset 自动生成 |
| 跨数据源 | 难以统一 | Loader 统一接口 |
| 测试友好性 | 依赖 DB | 可以 mock Loader |

## 五、如何迁移到 Entity-First 架构

### 5.1 迁移步骤

#### Step 1: 提取 Entity
```python
# 从现有的 ORM 模型中提取业务概念
class UserEntity(BaseModel):
    # 只保留业务字段，去掉 DB 特定字段
    id: int
    name: str
    email: str
    # 移除：password_hash, created_at, updated_at
```

#### Step 2: 定义 ERD
```python
# 集中定义实体关系
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(field='owner_id', target_kls=UserEntity, loader=user_loader),
    ]
```

#### Step 3: 重构 Response
```python
# 从 Entity 派生，而不是从 ORM
class TaskResponse(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'name'))
    owner: Annotated[Optional[UserSummary], LoadBy('owner_id')] = None
```

#### Step 4: 逐步替换
- 保留现有 ORM
- 新功能使用 Entity-First
- 旧接口逐步重构

### 5.2 注意事项
- 不要一次性重构所有代码
- 可以 ORM 和 Entity 并存
- 优先在新功能中使用 Entity-First
- 旧代码可以在维护时逐步迁移

## 六、常见问题（FAQ）

### Q1: Entity 不就是 ORM 的复制吗？
**A**: 不是，Entity 和 ORM 有本质区别：
- Entity 是业务概念，ORM 是 DB 映射
- Entity 可以表达 DB 无法表达的关系（跨数据源）
- Entity 可以包含计算字段，ORM 通常不包含
- Entity 是稳定的核心，ORM 是可替换的实现

### Q2: 这不会增加代码量吗？
**A**: 初期可能会增加，但长期收益更大：
- 消除了 ORM 和 Schema 的重复代码
- DefineSubset 自动生成 Response，减少手动维护
- Loader 可以复用，减少数据获取的重复逻辑

### Q3: 小项目也需要这样吗？
**A**: 取决于项目复杂度：
- 简单 CRUD 项目：ORM-First 足够
- 有复杂业务逻辑：建议 Entity-First
- 多数据源：强烈建议 Entity-First
- 团队协作：Entity-First 更易维护

### Q4: 如何处理写操作（POST/PUT/PATCH）？
**A**: 写操作和读操作不同：
- 写操作：仍然可以使用 ORM 或 Pydantic schema 作为 DTO
- 读操作：使用 Entity-First 获得架构优势
- 或者：定义专门的 CreateDTO/UpdateDTO，从 Entity 派生

## 七、总结

### 7.1 核心观点
1. **Pydantic schema 不应该是 ORM 的影子**
2. **建立独立的业务实体层**
3. **通过 Loader 解耦数据源**
4. **从 Entity 派生 API Response**

### 7.2 架构原则
- **分层清晰**：API → Domain → Data
- **单向依赖**：上层依赖下层，下层不依赖上层
- **独立演进**：各层可以独立修改而不影响其他层
- **类型安全**：通过 Entity 统一类型定义

### 7.3 pydantic-resolve 的角色
- 提供了 Entity-First 架构的工具支持
- 通过 ERD 管理实体关系
- 通过 DataLoader 优化数据获取
- 通过 DefineSubset 复用类型定义

### 7.4 呼吁
希望 FastAPI 社区能够重新思考 Pydantic 的使用方式，从 "ORM-First" 转向 "Entity-First"，建立更清晰的分层架构。

## 八、其他

### 8.1 SQLModel 能解决多少问题？

SQLModel 是一个试图统一 SQLAlchemy 和 Pydantic 的库，它让一个类同时作为数据库模型和 Pydantic schema 使用。这是一个实用的工具，但它是否能解决本文讨论的架构问题？让我们客观分析。

#### SQLModel 能解决的问题

**类型定义重复**：SQLModel 确实解决了最明显的问题——不需要在 ORM 模型和 Pydantic schema 中重复定义相同的字段。一个 `class User(SQLModel, table=True)` 定义既可以用作数据库表结构，也可以用作数据验证和序列化。修改字段时只需要改一个地方，避免了不一致的风险。

**字段同步问题**：由于只有单一定义源，字段名称、类型、默认值等自然会保持一致，不会出现 ORM 和 Schema 字段不匹配的情况。

#### SQLModel 无法解决的核心问题

**Schema 被动跟随 ORM 的本质未变**：SQLModel 的核心设计理念仍然是"ORM 先行"。它让 Pydantic schema 成为数据库模型的别名，而不是建立独立的业务实体层。数据库设计仍然直接决定 API 契约的结构，业务概念仍然被数据库表结构束缚。

**缺少独立的业务抽象层**：当使用 SQLModel 时，`class User` 表达的是"users 表"，而不是"用户这个业务概念"。如果数据库设计将 `owner_id` 和 `reporter_id` 合并为单个字段，API 契约也必须跟着改变。SQLModel 没有提供一个层次来表达稳定的业务概念，与可变的技术实现分离开来。

**多数据源统一处理能力缺失**：SQLModel 只能处理 SQLAlchemy 连接的数据源。当项目需要从数据库、RPC 服务、Redis 缓存、外部 API 等多个数据源组合数据时，SQLModel 无能为力。它没有提供统一的抽象层来处理不同格式的数据源。

**数据组装困境依然存在**：对于不使用 SQLAlchemy `relationship` 的场景，SQLModel 并没有提供更好的解决方案。开发者仍然需要手动编写查询、批量加载、构建映射、组装数据的代码，面临的 N+1 查询风险和代码重复问题完全相同。

**Schema 复用和组合机制缺失**：实际项目中，同一个实体往往需要不同的视图（比如用户列表只需要 ID 和姓名，用户详情需要完整信息）。SQLModel 没有提供从模型派生字段子集的机制，开发者要么复制定义，要么手动选择字段，又回到了类型重复和维护困难的老问题。

#### SQLModel 的定位

SQLModel 是一个实用的工具，它在 ORM-First 的框架内优化了开发体验，但它没有解决架构层面的根本问题。更准确地说，SQLModel 是"更优的 ORM-First 方案"，而不是 Entity-First 方案。

**适合使用 SQLModel 的场景**：简单的 CRUD 项目，单一数据源，API 契约可以跟随数据库结构变化的小型项目。在这些场景下，SQLModel 能够减少样板代码，提高开发效率。

**不适合使用 SQLModel 的场景**：复杂业务逻辑，需要稳定 API 契约的长期项目，多数据源集成的系统，需要清晰分层架构的团队协作项目。在这些场景下，Entity-First 架构（配合 pydantic-resolve）提供的独立业务实体层、统一的类型系统、灵活的数据加载机制，才是可持续发展的正确选择。

---

## 附录

### A. 完整示例项目
- 链接到 GitHub 仓库
- 展示完整的 Entity-First 项目结构

### B. 相关阅读
- Domain-Driven Design
- Clean Architecture
- GraphQL DataLoader 模式

### C. 工具推荐
- pydantic-resolve
- fastapi-voyager（可视化）
- SQLAlchemy（作为数据层之一）
