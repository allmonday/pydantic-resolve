# 重塑数据构建的开发体验：pydantic-resolve vs SQLAlchemy ORM 查询对比

## 背景

后端开发写得最多的是什么？大概就是从数据库里把数据捞出来，组装成嵌套的 JSON 返回给前端。

比如一个敏捷项目管理的 API，前端想要这样的数据：

```json
{
  "id": 1,
  "name": "Sprint 24",
  "stories": [
    {
      "id": 10,
      "title": "User login",
      "tasks": [
        {
          "id": 100,
          "title": "Design login page",
          "owner": { "id": 1, "name": "Ada" }
        }
      ]
    }
  ]
}
```

四层嵌套：Sprint -> Story -> Task -> User。不算特别深，但也够让人头疼了。

SQLAlchemy ORM 的 relationship + eager loading 当然能搞定，但随着嵌套层级加深、同一份数据要应付的 API 变体越来越多，你会发现 options 链越写越长、维护成本越来越高。

[pydantic-resolve](https://github.com/allmonday/pydantic-resolve) 是另一种思路。它基于 Pydantic 模型，借鉴了 GraphQL DataLoader 的批量加载模式，让你用声明式的方式描述"数据长什么样"，由框架自动递归遍历、批量查询、组装嵌套结构。不需要手写 options 链，不需要操心 N+1，Schema 本身就是加载逻辑的唯一定义。

本文通过三个递进的场景，让两种方案的代码自己说话——看看 ORM eager loading 和 pydantic-resolve 在实际开发中体验究竟差在哪。

---

## 先看地基：共用的 SQLAlchemy Model

先说清楚一件事：pydantic-resolve 不是来取代 SQLAlchemy 的。它的 loader 里面跑的就是 SQLAlchemy 查询，两种方案共享同一套 ORM Model。区别只在于拿到数据之后怎么组装。

```python
# models.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(50))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    story_id: Mapped[int] = mapped_column(ForeignKey("stories.id"))

    owner: Mapped["User"] = relationship(lazy="raise")
    story: Mapped["Story"] = relationship(back_populates="tasks", lazy="raise")


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(50))
    sprint_id: Mapped[int] = mapped_column(ForeignKey("sprints.id"))

    tasks: Mapped[list["Task"]] = relationship(back_populates="story", lazy="raise")
    sprint: Mapped["Sprint"] = relationship(back_populates="stories", lazy="raise")


class Sprint(Base):
    __tablename__ = "sprints"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))

    stories: Mapped[list["Story"]] = relationship(back_populates="sprint", lazy="raise")
```

注意所有 relationship 都设了 `lazy="raise"`——谁敢偷偷懒加载，直接报错。这迫使两种方案都必须显式声明"我要加载什么"，对比更公平。

---

## 场景一：全层级加载

**需求**：Sprint 列表页，每个 Sprint 嵌套所有 Story，每个 Story 嵌套所有 Task，每个 Task 带上 owner。四层一口气全拿下来。

### SQLAlchemy ORM 方式

```python
from typing import Optional
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from models import Sprint, Story, Task


# ---- Pydantic Schema（用于序列化 ORM 对象）----

class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class TaskSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    status: str
    owner_id: int
    owner: Optional[UserSchema] = None


class StorySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    status: str
    tasks: list[TaskSchema] = []


class SprintSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    stories: list[StorySchema] = []


# ---- 查询 ----

async def get_sprints_full_orm(session: AsyncSession) -> list[dict]:
    stmt = (
        select(Sprint)
        .options(
            selectinload(Sprint.stories)
            .selectinload(Story.tasks)
            .joinedload(Task.owner)
        )
        .order_by(Sprint.id)
    )

    result = await session.execute(stmt)
    sprints = result.scalars().unique().all()

    return [SprintSchema.model_validate(s).model_dump() for s in sprints]
```

写这段代码的时候，脑子里需要同时装好几件事。

首先是 options 链——4 层数据对应 3 级链式配置：`Sprint.stories` -> `Story.tasks` -> `Task.owner`，漏掉任何一级，`lazy="raise"` 会直接炸掉，`model_validate` 也没法读未加载的关系。然后每一级你得在 `joinedload`（JOIN 查询）和 `selectinload`（独立 IN 查询）之间做选择，这要求你理解它们在 SQL 生成上的差异。选了 `joinedload` 还不能忘记调 `.unique()`，因为 JOIN 会产生重复的父行。

最让人不舒服的是，Schema 和 options 链形成了隐式耦合——Schema 里声明了 `stories: list[StorySchema]`，options 里就得有对应的 `selectinload(Sprint.stories)`。改了一处忘了另一处，运行时才会发现。

### pydantic-resolve 方式

```python
from typing import Optional
from pydantic import BaseModel, ConfigDict
from pydantic_resolve import Resolver, Loader, build_list, build_object
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from models import Sprint as SprintModel
from models import Story as StoryModel
from models import Task as TaskModel
from models import User as UserModel


# async_session: async_sessionmaker  (应用启动时初始化)


# ---- Loaders: 每种关系定义一次，全局复用 ----

async def story_batch_loader(sprint_ids: list[int]):
    async with async_session() as session:
        stmt = select(StoryModel).where(StoryModel.sprint_id.in_(sprint_ids))
        rows = (await session.scalars(stmt)).all()
    return build_list(rows, sprint_ids, lambda s: s.sprint_id)


async def task_batch_loader(story_ids: list[int]):
    async with async_session() as session:
        stmt = select(TaskModel).where(TaskModel.story_id.in_(story_ids))
        rows = (await session.scalars(stmt)).all()
    return build_list(rows, story_ids, lambda t: t.story_id)


async def user_batch_loader(user_ids: list[int]):
    async with async_session() as session:
        stmt = select(UserModel).where(UserModel.id.in_(user_ids))
        rows = (await session.scalars(stmt)).all()
    return build_object(rows, user_ids, lambda u: u.id)


# ---- View Schema: 声明数据形状 ----

class UserView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class TaskView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    status: str
    owner_id: int

    owner: Optional[UserView] = None
    def resolve_owner(self, loader=Loader(user_batch_loader)):
        return loader.load(self.owner_id)


class StoryView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    status: str

    tasks: list[TaskView] = []
    def resolve_tasks(self, loader=Loader(task_batch_loader)):
        return loader.load(self.id)


class SprintView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

    stories: list[StoryView] = []
    def resolve_stories(self, loader=Loader(story_batch_loader)):
        return loader.load(self.id)


# ---- 查询入口 ----

async def get_sprints_full_resolve() -> list[dict]:
    async with async_session() as session:
        stmt = select(SprintModel).order_by(SprintModel.id)
        rows = (await session.scalars(stmt)).all()

    sprints = [SprintView.model_validate(s) for s in rows]
    sprints = await Resolver().resolve(sprints)
    return [s.model_dump() for s in sprints]
```

换成 pydantic-resolve 之后，画风完全不同。

入口查询变成了朴素的 `select(Sprint)`——不需要任何 options。每层关系由各自 Schema 的 `resolve_*` 方法声明，Resolver 会自动递归往下走。更重要的是，所有同类加载请求会被 DataLoader 自动合并成一条 `WHERE ... IN (...)` 查询，天然防止 N+1，你根本不需要操心。

还有一个微妙但关键的区别：ORM 方式下 Schema 和 options 链是两处独立的定义，需要人肉保持同步；而 pydantic-resolve 的 Schema 本身就包含加载逻辑（`resolve_*`），一处定义、一处维护，改了 Schema 就改了加载行为。Loader 也是全局复用的——`story_batch_loader`、`task_batch_loader`、`user_batch_loader` 写一次，所有 endpoint 直接拿来用。

### 场景一小结

| 维度 | SQLAlchemy ORM | pydantic-resolve |
|------|---------------|------------------|
| 入口查询 | `select(Sprint).options(...)` 3 级链式配置 | `select(Sprint)` 平铺查询 |
| 加载策略 | 每层需选择 joinedload/selectinload | 每个 loader 独立使用 `WHERE IN` |
| 维护点 | Schema + options 链两处同步 | Schema 一处包含加载声明 |
| N+1 安全 | 依赖 options 链配置正确 | DataLoader 自动批量 |

---

## 场景二：部分加载（精简字段）

**需求**：Sprint 列表页只想展示每个 Story 的 title 和 status，Task 那一层完全不需要。典型的"列表视图只要概要信息"场景。

### SQLAlchemy ORM 方式

```python
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import selectinload, load_only, noload
from sqlalchemy.ext.asyncio import AsyncSession

from models import Sprint, Story


class StoryBriefSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    title: str
    status: str


class SprintBriefSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    stories: list[StoryBriefSchema] = []


async def get_sprints_brief_orm(session: AsyncSession) -> list[dict]:
    stmt = (
        select(Sprint)
        .options(
            selectinload(Sprint.stories)
            .load_only(Story.title, Story.status)
            .noload(Story.tasks)
        )
        .order_by(Sprint.id)
    )

    result = await session.execute(stmt)
    sprints = result.scalars().unique().all()

    return [SprintBriefSchema.model_validate(s).model_dump() for s in sprints]
```

这里要同时摆弄两个正交的概念：`load_only(Story.title, Story.status)` 控制的是**加载哪些列**，而 `noload(Story.tasks)` 控制的是**阻断哪些关系**。

严格来说，`model_validate` 只会访问 Schema 里声明的字段，不写 `noload` 在这个例子里不会立刻报错。但在实际项目中，`noload` 仍然是推荐做法——如果后续有人在同一个 session 上下文里不小心访问了 `story.tasks`（比如日志、序列化中间件、或者调试时的 `repr`），`lazy="raise"` 就会炸。显式阻断是一种防御性编程习惯。

不过这也带来了额外的心智负担：options 链不仅要声明"我要什么"（`load_only`），还得考虑"我要不要显式阻断什么"（`noload`）。每多一个视图变体，就多一套 options 链和配套 Schema。

### pydantic-resolve 方式

```python
from pydantic import BaseModel, ConfigDict
from pydantic_resolve import Resolver, Loader
from sqlalchemy import select

from models import Sprint as SprintModel


class StoryBriefView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    title: str
    status: str
    # 没有 resolve_tasks 方法 —— 不声明就不加载


class SprintBriefView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

    stories: list[StoryBriefView] = []
    def resolve_stories(self, loader=Loader(story_batch_loader)):
        return loader.load(self.id)


async def get_sprints_brief_resolve() -> list[dict]:
    async with async_session() as session:
        stmt = select(SprintModel).order_by(SprintModel.id)
        rows = (await session.scalars(stmt)).all()

    sprints = [SprintBriefView.model_validate(s) for s in rows]
    sprints = await Resolver().resolve(sprints)
    return [s.model_dump() for s in sprints]
```

不声明 `resolve_tasks` 就不会加载 Task 层——这是"白名单"思维，跟 ORM 的"黑名单"思维（`noload` 显式阻断）形成鲜明对比。

但你可能会问：`story_batch_loader` 里还是 `select(StoryModel)` 全字段查询吧？`StoryBriefView` 只要 `title` 和 `status` 两个字段，剩下的不是白查了？

这就是 `_query_meta` 发挥作用的地方。Resolver 在初始化 DataLoader 实例时，会根据目标 Schema 的字段声明自动收集元信息，设置到 loader 实例的 `_query_meta` 属性上。手写 loader 可以读取它来优化查询：

```python
async def story_batch_loader(sprint_ids: list[int]):
    async with async_session() as session:
        stmt = select(StoryModel).where(StoryModel.sprint_id.in_(sprint_ids))

        # self._query_meta['fields'] 由 Resolver 根据 Schema 自动收集
        # StoryBriefView 只声明了 title, status → fields = ['title', 'status']
        fields = getattr(story_batch_loader, '_query_meta', {}).get('fields')
        if fields:
            # 只查需要的列 + FK 列
            columns = [getattr(StoryModel, f) for f in fields] + [StoryModel.sprint_id]
            stmt = stmt.options(load_only(*columns))

        rows = (await session.scalars(stmt)).all()
    return build_list(rows, sprint_ids, lambda s: s.sprint_id)
```

手写 loader 需要自己读 `_query_meta` 来做这个优化，稍显麻烦。后文会介绍 `build_relationship` 自动生成 loader 的方案，auto-generated loader 内部已经内置了这个逻辑——换个精简 Schema 就自动少查列，不需要你动 loader 代码。

这就是 ORM 和 pydantic-resolve 在部分加载上最本质的区别：ORM 需要你在 options 链里**手动声明** `load_only` + `noload` 来裁剪查询；pydantic-resolve 通过 Schema 字段声明**自动推导**出需要查哪些列、加载哪些关系——Schema 就是查询优化的唯一 source of truth。

### 场景二小结

| 维度 | SQLAlchemy ORM | pydantic-resolve |
|------|---------------|------------------|
| 精简字段 | `load_only(...)` 手动指定列 | Schema 字段自动推导 `_query_meta`，loader 按需查询 |
| 阻断关系 | `noload(...)` 显式阻断 | 不写 `resolve_*` 即不加载 |
| 心智模型 | 黑名单：同时声明要什么和不要什么 | 白名单：Schema 声明了什么就查什么 |
| 新增变体成本 | 新 options 链 + 新 Schema | 新 Schema，复用 loader，自动优化查询 |

---

## 场景三：派生字段计算

**需求**：Sprint 详情页需要额外展示 `total_task_count`（跨所有 Story 的 Task 总数）和 `contributor_names`（去重排序的任务负责人）。这两个字段数据库里没有，得从嵌套数据里算出来。

### SQLAlchemy ORM 方式

```python
from typing import Optional
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from models import Sprint, Story, Task


# ---- Pydantic Schema ----

class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class TaskSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    status: str
    owner_id: int
    owner: Optional[UserSchema] = None


class StorySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    status: str
    tasks: list[TaskSchema] = []


class SprintStatsSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    stories: list[StorySchema] = []
    total_task_count: int = 0
    contributor_names: list[str] = []


# ---- 查询 + 手动计算派生字段 ----

async def get_sprints_with_stats_orm(session: AsyncSession) -> list[dict]:
    # 计算派生字段需要全量加载
    stmt = (
        select(Sprint)
        .options(
            selectinload(Sprint.stories)
            .selectinload(Story.tasks)
            .joinedload(Task.owner)
        )
        .order_by(Sprint.id)
    )

    result = await session.execute(stmt)
    sprints = result.scalars().unique().all()

    output = []
    for sprint in sprints:
        schema = SprintStatsSchema.model_validate(sprint)

        # 派生字段需要手动遍历计算
        total = 0
        contributors: set[str] = set()
        for story in schema.stories:
            for task in story.tasks:
                total += 1
                if task.owner:
                    contributors.add(task.owner.name)

        schema.total_task_count = total
        schema.contributor_names = sorted(contributors)
        output.append(schema.model_dump())

    return output
```

到这里问题就比较扎眼了。

哪怕你只是想要两个汇总数字，options 链也得跟场景一一模一样——因为计算 `total_task_count` 必须先把 Task 全部加载进来。`model_validate` 帮你处理了嵌套序列化，但派生字段没有任何生命周期钩子，只能在外面用 for 循环手动算完再塞回去。

更麻烦的是，这段遍历逻辑和查询代码混在同一个函数里。如果另一个接口也需要 `total_task_count`，你要么复制粘贴这段循环，要么自己抽一个 helper。而且每新增一个派生字段，这个函数就膨胀一圈——`overdue_count`、`avg_tasks_per_story`……想想就头大。

### pydantic-resolve 方式

```python
from pydantic import BaseModel, ConfigDict
from pydantic_resolve import Resolver, Loader


class SprintDetailView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

    stories: list[StoryView] = []  # 复用场景一定义的 StoryView
    def resolve_stories(self, loader=Loader(story_batch_loader)):
        return loader.load(self.id)

    # ---- 派生字段 ----

    total_task_count: int = 0
    def post_total_task_count(self):
        return sum(len(story.tasks) for story in self.stories)

    contributor_names: list[str] = []
    def post_contributor_names(self):
        names: set[str] = set()
        for story in self.stories:
            for task in story.tasks:
                if task.owner:
                    names.add(task.owner.name)
        return sorted(names)


async def get_sprints_with_stats_resolve() -> list[dict]:
    async with async_session() as session:
        stmt = select(SprintModel).order_by(SprintModel.id)
        rows = (await session.scalars(stmt)).all()

    sprints = [SprintDetailView.model_validate(s) for s in rows]
    sprints = await Resolver().resolve(sprints)
    return [s.model_dump() for s in sprints]
```

`post_*` 是这个场景下最关键的能力。框架保证了一个简单但重要的时序：**所有 `resolve_*`（包括子孙节点的）全部跑完之后，才会执行 `post_*`**。

所以当 `post_total_task_count` 执行的时候，`self.stories` 已经是填充好的 `StoryView` 列表，每个 Story 里的 `tasks` 也已经是带着 `owner` 信息的 `TaskView`。你不需要操心"数据到底加载完了没有"这件事——框架替你保证了。

想加新的派生字段？写一个 `post_*` 方法就行，每个方法自包含、互不干扰，甚至可以单独构造 Pydantic 对象来做单元测试。

### 场景三小结

| 维度 | SQLAlchemy ORM | pydantic-resolve |
|------|---------------|------------------|
| 派生逻辑位置 | 散落在查询函数中，手动赋值到 Schema | `post_*` 方法，与字段定义同处一个 Schema |
| 执行时序保证 | 开发者手动确保先加载再计算 | 框架保证：resolve_* 全部完成后执行 post_* |
| 新增派生字段 | 修改同一个函数，添加更多遍历逻辑 | 添加独立的 `post_*` 方法 |
| 可复用性 | 需抽取 helper 函数 | Schema 继承/组合即可复用 |
| 可测试性 | 需 mock 完整 ORM 查询链 | 构造 Pydantic 对象直接测试 `post_*` |

---

## 更进一步：用 ER Diagram 干掉手写 Loader

前面三个场景里，pydantic-resolve 那边的 loader 虽然全局复用，但毕竟还是手写的——`story_batch_loader`、`task_batch_loader`、`user_batch_loader` 各写一遍 `select ... where ... in_`，模式高度重复。你可能已经在想：这些 loader 的逻辑不就是 SQLAlchemy ORM relationship 里已经描述过的关系吗？能不能直接从 ORM 的 relationship 元信息自动生成？

答案是可以。pydantic-resolve 提供了 `build_relationship`，它会检查 SQLAlchemy ORM 的 relationship 定义，自动为每种关系（多对一、一对多、多对多）生成对应的 DataLoader，省去了手写 loader 的过程。

```python
from typing import Annotated, Optional
from pydantic import BaseModel, ConfigDict
from pydantic_resolve import Resolver, config_global_resolver, ErDiagram, DefineSubset
from pydantic_resolve.integration.sqlalchemy import build_relationship
from pydantic_resolve.integration.mapping import Mapping
from sqlalchemy import select

from models import Sprint as SprintModel, Story as StoryModel, Task as TaskModel, User as UserModel


# ---- Step 1: 定义 DTO，对齐 ORM 的基础字段 ----

class UserDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

class TaskDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    status: str
    owner_id: int
    story_id: int

class StoryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    status: str
    sprint_id: int

class SprintDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


# ---- Step 2: 从 ORM relationship 自动生成关系和 Loader ----

entities = build_relationship(
    mappings=[
        Mapping(entity=UserDTO,   orm=UserModel),
        Mapping(entity=TaskDTO,   orm=TaskModel),
        Mapping(entity=StoryDTO,  orm=StoryModel),
        Mapping(entity=SprintDTO, orm=SprintModel),
    ],
    session_factory=lambda: async_session(),
)

diagram = ErDiagram(entities=[]).add_relationship(entities)
AutoLoad = diagram.create_auto_load()
config_global_resolver(diagram)


# ---- Step 3: 用 AutoLoad 注解替代手写 resolve_* ----

class UserView(UserDTO):
    pass

class TaskView(TaskDTO):
    owner: Annotated[Optional[UserDTO], AutoLoad()] = None

class StoryView(StoryDTO):
    tasks: Annotated[list[TaskView], AutoLoad()] = []

class SprintView(SprintDTO):
    stories: Annotated[list[StoryView], AutoLoad()] = []


# ---- 查询入口：和之前完全一样 ----

async def get_sprints_full() -> list[dict]:
    async with async_session() as session:
        stmt = select(SprintModel).order_by(SprintModel.id)
        rows = (await session.scalars(stmt)).all()

    sprints = [SprintView.model_validate(s) for s in rows]
    sprints = await Resolver().resolve(sprints)
    return [s.model_dump() for s in sprints]
```

对比一下前面手写 loader 的版本：`story_batch_loader`、`task_batch_loader`、`user_batch_loader` 三个函数大约 20 行代码，每个 Schema 里还要写对应的 `resolve_*` 方法。现在这些全部被 `build_relationship` + `AutoLoad()` 替代了——`build_relationship` 从 ORM 的 relationship 元信息里读取外键关系，自动生成批量 loader；`AutoLoad()` 注解告诉 Resolver "这个字段按 ER 关系自动加载"，连 `resolve_*` 方法都不用写了。

整个过程的心智模型变成了：**ORM Model 定义关系 -> DTO 定义字段 -> `AutoLoad` 连接两者 -> Resolver 自动编排**。关系声明只在 ORM 里写一次，不需要在 loader 里重复表达。

### 用 DefineSubset 裁剪响应字段

不过你可能注意到了一个小问题：上面的 `TaskView` 继承了 `TaskDTO` 的全部字段，包括 `owner_id` 和 `story_id` 这些外键字段。对 API 消费者来说，这些 FK 字段是内部实现细节，不应该暴露在响应里。

手动去 override 每个字段比较笨拙。pydantic-resolve 提供了 `DefineSubset` 来解决这个问题——从 DTO 里挑选你想暴露的字段，自动隐藏其余的，同时保留 ER 关系元信息让 `AutoLoad` 继续工作：

```python
from pydantic_resolve import DefineSubset


# 只暴露 id, title, status —— owner_id, story_id 自动隐藏
class TaskView(DefineSubset):
    __subset__ = (TaskDTO, ['id', 'title', 'status'])
    owner: Annotated[Optional[UserDTO], AutoLoad()] = None


# 只暴露 id, title, status —— sprint_id 自动隐藏
class StoryView(DefineSubset):
    __subset__ = (StoryDTO, ['id', 'title', 'status'])
    tasks: Annotated[list[TaskView], AutoLoad()] = []


class SprintView(SprintDTO):
    stories: Annotated[list[StoryView], AutoLoad()] = []

    total_task_count: int = 0
    def post_total_task_count(self):
        return sum(len(story.tasks) for story in self.stories)
```

`DefineSubset` 做了几件事情：`(TaskDTO, ['id', 'title', 'status'])` 声明只暴露这三个字段；而 `AutoLoad()` 需要的 `owner_id` 外键字段会被自动注入并标记为 `exclude=True`——它存在于对象内部供 loader 使用，但 `model_dump()` 时不会出现在输出里。

这样最终的 API 响应是干净的：

```json
{
  "id": 1, "name": "Sprint 24",
  "total_task_count": 2,
  "stories": [
    {
      "id": 10, "title": "User login", "status": "in_progress",
      "tasks": [
        { "id": 100, "title": "Design login page", "status": "todo",
          "owner": { "id": 1, "name": "Ada" } }
      ]
    }
  ]
}
```

没有 `owner_id`、`story_id`、`sprint_id` 这些 FK 字段泄漏出去。DTO 保持了完整的字段定义供内部使用，`DefineSubset` 按需裁剪出干净的 API 视图。

当然，`post_*` 那些派生字段的逻辑还是手写的，`AutoLoad` 只解决 FK 关系的自动遍历，业务计算仍然由你自己声明。但光是 `build_relationship` 省掉手写 loader、`AutoLoad` 省掉 `resolve_*` 方法、`DefineSubset` 省掉手动裁剪字段这三步，在实体数量多的项目里就已经能大幅减少重复代码了。

---

## 总结对比

| 维度 | SQLAlchemy ORM Eager Loading | pydantic-resolve |
|------|------------------------------|------------------|
| **全量加载** | options 链必须精确匹配嵌套深度 | 每层独立声明，Resolver 自动编排 |
| **部分加载** | `load_only` + `noload` 组合 | 不同 Schema 复用相同 loader |
| **派生字段** | 手动遍历，外部赋值到 Schema | `post_*` 方法，框架保证执行时序 |
| **新增变体成本** | 新 options 链 + 新 Schema (~25行) | 新 Schema (~15行)，复用 loader |
| **N+1 安全性** | 依赖 options 配置完整正确 | DataLoader 自动批量，天然安全 |
| **心智模型** | 配置查询以匹配期望输出 | 声明输出形状，让框架填充 |
| **维护点** | Schema 定义 + options 链两处同步 | Schema 一处包含加载 + 后处理逻辑 |

## 结语

首先，这两者**不是互斥的**。pydantic-resolve 的 loader 里面跑的就是 SQLAlchemy 查询，ORM Model 是共用的。你完全可以在现有的 ORM 项目里渐进式地引入 pydantic-resolve——哪个接口嵌套最深、变体最多，就先从哪个开始改。

两种方案的核心差异说到底是**思考方式不同**。用 ORM eager loading 的时候，你脑子里想的是"我该怎么配置查询来凑出想要的数据结构？"——这是查询导向。而用 pydantic-resolve 的时候，你想的是"我期望的数据结构长什么样？"——这是描述导向。后者其实更接近 API 设计的本质：先定义接口契约，再让工具去填充。

当然，2 层嵌套、1 个接口的场景下，ORM eager loading 完全够用，没必要引入额外的抽象。但一旦嵌套到 3-4 层、同一份数据要支撑列表视图、详情视图、统计视图等多个变体，pydantic-resolve 的 loader 复用 + Schema 组合的优势就开始滚雪球了——每多一个变体，你只需要多写一个 Schema，而不是再配一遍 options 链。
