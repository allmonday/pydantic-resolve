# Entity-First Architecture: The Missing Piece in FastAPI Development

## 1. Introduction: The Overlooked Architectural Problem

### 1.1 Current State Observations

FastAPI has become one of the preferred frameworks for Python web development, and its deep integration with Pydantic has made data validation simpler than ever. However, after browsing through numerous FastAPI projects, official templates, community tutorials, and best practice guides, we discovered a striking similarity: almost all projects follow the same pattern—first define SQLAlchemy ORM models, then create Pydantic schemas based on these models.

This "ORM-first, Pydantic-follows" pattern has become so ubiquitous that many developers have never questioned its rationality. The official full-stack template adopts this approach, community best practice repositories with thousands of stars recommend it, and numerous tutorials and articles teach it. But this doesn't mean it's correct.

When we deeply analyze the practical application of this pattern, some deep-seated issues begin to surface. Pydantic schemas passively copy field definitions from ORM models, resulting in type definitions being duplicated in two places; any change to the database design directly affects API contracts; business concepts are deeply permeated by database structure, making it difficult to express the true semantics of domain models; when data needs to be combined from multiple data sources (databases, RPC, caches, etc.), the code becomes exceptionally complex and hard to maintain.

The root of these problems lies in our confusion between two different levels of abstraction: database models (ORM) and domain models (Entity). ORM models should only be implementation details of data persistence, not the center of the entire architecture. Pydantic schemas shouldn't be shadows of ORM either, but should become independent abstraction layers that express business concepts and API contracts.

### 1.2 Core Arguments

The core argument of this article is simple: Pydantic schemas shouldn't be shadows of ORM, but should be built on an independent business entity layer. This is not just a code organization issue, but a systemic issue concerning architectural clarity, maintainability, and long-term evolution.

**Domain models are the core of architecture**. Business entities (Entity) should express pure domain concepts, such as "user", "task", "project", rather than database tables. These entities define the structure of business objects and their relationships, independent of any technical implementation. When we talk about business, we're saying "which user does this task belong to", "which tasks are included in this project", not "the tasks table has a user_id foreign key". The existence of domain models allows us to think and design systems in business language, rather than being bound by technical implementation details.

**Specific use cases drive API design**. Each API endpoint serves a specific business scenario, such as "the user list page needs the user's id and name", "the task detail page needs complete task information and detailed information about the person in charge". These use cases determine what data the API should return, not what fields the database has. Pydantic schemas should be defined based on specific use cases, selecting needed fields from domain models, adding use-case-specific computed fields and validation logic. This is the true meaning of "response models".

**The data layer is just an implementation detail**. Whether data is stored in databases like PostgreSQL, MySQL, MongoDB, or read from caches like Redis, Memcached, or obtained from external services through gRPC, REST API, none of these should affect the definition of domain models and API contracts. The data layer is responsible for efficiently and reliably fetching data, but it's just a replaceable implementation detail. Database structures may change, external services may migrate, caching strategies may adjust, but as long as the data layer can provide the data needed by domain models, these changes shouldn't spread to business logic and API contracts.

The core value of this layered architecture lies in **stability and evolvability**. Domain models serve as a stable core, existing independently of specific implementations. API contracts are designed based on use cases, providing stable interfaces for the frontend. The data layer serves as a replaceable shell that can be flexibly adjusted according to performance requirements, technology stack upgrades, and business changes. When these three levels are clearly separated, the system gains the ability to evolve continuously—we can optimize data access strategies without affecting business logic, refactor data models without breaking API contracts, and adjust API design without changing domain models.

This is not just theoretical elegance, but practical necessity. When project scale grows, business complexity increases, and team collaboration needs increase, clear layered architecture becomes a key factor in whether a project can continue to evolve. A system deeply permeated by database structure requires touching everything with every database change; while a system built on stable domain models can more calmly cope with changes.

## 2. Architectural Problems of "ORM-First"

### 2.1 Typical Project Structure

In most FastAPI projects, you'll see a similar organizational approach:

```
project/
├── models/
│   ├── user.py          # ORM models (database table structure)
│   ├── task.py
│   └── ...
├── schemas/
│   ├── user.py          # Pydantic schemas (copy fields from ORM)
│   ├── task.py
│   └── ...
├── routes/
│   └── ...
└── services/
    └── ...
```

This structure looks reasonable—data models and API contracts are stored separately—but the problem is that Pydantic schemas are often just passive copies of database models, with field names, types, and even almost identical comments. The deeper problem is that the entire project stratification has gaps: from database models to Pydantic schemas, there's no independent business concept layer.

### 2.2 Core Problem Analysis

#### Problem 1: Schemas Passively Follow ORM

When a project's Pydantic schemas are just shadows of database models, a series of deep problems emerge. The most obvious is the duplication of type definitions: the same field names, same type constraints, defined and maintained in two different places. This duplication violates the DRY (Don't Repeat Yourself) principle in software development, but more seriously it exposes an essential chaos in architecture—API contracts shouldn't be limited by the physical design of the database.

Consider an actual scenario: storing user password hashes in the database is for authentication needs, this field is a database implementation detail, and API responses should completely not include it. To avoid exposing this field, developers have to additionally define a Pydantic schema that doesn't include `password_hash`.

This approach brings two problems:

**First, tedious repetitive definitions**: You need to maintain two almost identical classes—one ORM model containing all fields, one Pydantic schema manually excluding sensitive fields. When a user has 20 fields, you need to define these 20 fields repeatedly, just to exclude 1 of them.

If developers try to extract common classes to reduce duplication, they face new troubles: extraction criteria are vague. For example, which fields should be put in a common `UserBase`? Which fields are needed in all scenarios? Which fields are only needed in specific scenarios? When different API endpoints have widely varying field requirements (some need `email`, some need `phone`, some need neither), the definition of common classes becomes difficult to decide, and maintenance costs are higher instead.

**Second, maintenance burden when modifying**: When the database adds new fields (e.g., adding `phone`) or modifies field types (e.g., changing `name` from `String(50)` to `String(100)`), you need to modify both ORM models and Pydantic schemas, easily missing or creating inconsistencies. Even worse, when you have multiple different response scenarios (user summary, user detail, user avatar info), each scenario needs to manually copy and maintain field subsets.

This violates a basic principle: APIs should be stable external contracts, while database implementation is internal details that can be optimized. ORM-First architecture tightly couples these two, and any database change directly affects API contracts.

#### Problem 2: Business Concepts Permeated by Database Structure

When database structure becomes the center of the entire architecture, business concepts are also bound by database design details. A typical example is the concepts of "owner" and "reporter" in task management systems.

**Business perspective**: From a business perspective, these are two clear roles—a task has an owner and a reporter. These are natural concepts in the business domain.

**Database design decision**: In database design, this might be implemented in various ways: two foreign key fields (`owner_id` and `reporter_id`), a single `user_id` plus `role` field, or a many-to-many relationship table. These are purely technical decisions, depending on performance requirements, data volume, query patterns, and other factors.

When APIs directly expose database structure, business concepts are replaced by technical details, which violates the **Law of Demeter** in software engineering: the encapsulation of one level should let upper-level users know as little as possible. Frontend as API users only needs to know business concepts ("task has an owner"), not how data is stored ("stored in two fields").

```python
# Database design 1: using two foreign keys
class TaskORM(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    title = Column(String(100))
    owner_id = Column(Integer, ForeignKey('users.id'))      # owner
    reporter_id = Column(Integer, ForeignKey('users.id'))   # reporter

# API Schema passively copies DB structure
class TaskResponse(BaseModel):
    id: int
    title: str
    owner_id: int          # frontend must know what this is
    reporter_id: int       # frontend must know what this is
    owner: Optional['UserResponse']
    reporter: Optional['UserResponse']
```

The problem now is: frontend developers need to understand the difference between `owner_id` and `reporter_id`, and need to know why there are two fields. These are database design details, unrelated to business concepts. If later the database team decides to refactor the table structure (e.g., merging two fields into one for performance), the API must also change, and frontend code needs corresponding adjustments.

```python
# Database design 2: refactored to single field + role
class TaskORM(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    title = Column(String(100))
    user_id = Column(Integer, ForeignKey('users.id'))   # merged field
    role = Column(String(20))  # 'owner' or 'reporter'

# API Schema must change accordingly
class TaskResponse(BaseModel):
    id: int
    title: str
    user_id: int           # now changed to user_id
    role: str              # added role field
    # frontend code must all be modified!
```

This change is unrelated to business—business still has two roles of "owner" and "reporter"—but purely technical decisions (database refactoring) affect all levels of the system, including frontend applications. This is a direct consequence of business concepts being permeated by database structure.

True business concepts—"who does this task belong to", "who is responsible for following up on this task"—are drowned in technical details like foreign key relationships and table structures. We can't use business language to think and design APIs, but must always consider how the database stores this data. This confusion of concepts makes code difficult to understand and maintain, and new team members need to understand database design before understanding business logic.

#### Problem 3: Data Assembly Dilemma When Unable to Use Relationship Mapping

SQLAlchemy provides `relationship` functionality that can automatically load associated data when querying, which looks convenient. But in actual projects, this functionality is not omnipotent. It's powerless for cross-database queries, difficult to use under complex JOIN conditions, read-only queries or report queries that need performance optimization are often also not suitable for using it. Once脱离 the convenience of `relationship`, developers must manually write lengthy data assembly code.

This process usually contains multiple repetitive steps: first query main data (e.g., article list), then collect all associated IDs (e.g., author IDs of all articles), then batch query associated data (e.g., query users by ID list), then manually build ID to object mapping dictionary, finally loop through main data, manually find corresponding associated objects and assemble into final response structure. This process has large code volume, is error-prone, and needs to be written repeatedly every time similar associated queries are needed.

More dangerously, manually writing this code easily produces performance problems. If developers forget batch queries and query associated data individually in a loop, they immediately fall into the classic N+1 query trap—originally a problem that could be solved with one batch query becomes N independent queries. When data volume increases, performance problems quickly emerge. While using `relationship` can avoid this problem, it returns to the previously mentioned dilemma: not all scenarios are suitable for using it.

This data assembly logic is scattered throughout the project, and each API endpoint that needs associated data might have a similar piece of code. This not only violates the single responsibility principle, but also makes code difficult to reuse and test. When needing to optimize data loading strategies (e.g., adding caching, adjusting query order), modifications are needed in multiple places, easily missed or creating inconsistencies.

#### Problem 4: Difficulty in Unified Handling of Multiple Data Sources

The complexity of modern applications lies in data often not coming from just one place. User information might be in a PostgreSQL database, order data might be in MongoDB, inventory status might need to be obtained by calling external RPC services, recommendation lists might be read from Redis cache. When these data need to be combined into a unified API response, traditional approaches reveal obvious deficiencies.

Each data source has its own data format and access method. Databases return ORM objects, RPC services return dictionaries or custom objects, caches return serialized strings or byte streams. To unify them into Pydantic schemas, developers need to write various conversion functions, handling field mapping, type conversion, data extraction and other details. These conversion logics are scattered in various places, difficult to centrally manage and optimize.

Even worse, when a data source needs to be migrated or upgraded (e.g., migrating user service from database to independent microservice), all conversion code involving that data source needs modification. Since these conversion logics are mixed with business logic, the impact scope of modifications is difficult to assess, and testing costs are high. Lack of a unified abstraction layer makes it difficult for the system to cope with data source changes, and every change might affect everything.

#### Problem 5: Schemas Difficult to Reuse and Compose

In actual projects, the same entity often needs to appear in different forms in different scenarios. User list pages might only need to display user ID and name, user detail pages need to display complete information including email, phone, registration time, etc., user info embedded in task lists might only need ID and avatar URL. If defining a separate Pydantic schema for each scenario, there will be a large amount of duplicate definitions, and field type modifications need to synchronize multiple places.

In traditional approaches, developers either copy-paste code (violating DRY principle), or try to use inheritance for composition (but Pydantic's inheritance mechanism is not intuitive, easily creating confusion). The deeper problem is that there's no clear "belong to the same entity" relationship between these schemas—from the code perspective, `UserSummary`, `UserDetail`, `UserIdOnly` are three independent classes, and it's not intuitive to see that they're all different views of the "user" business entity.

This lack of unified schema definition makes code difficult to maintain. When an entity's field types need modification (e.g., changing user ID from integer to UUID), all related schema definitions need to be searched and modified one by one, easily missed. There's also no type system to guarantee the consistency of these schemas—the compiler won't tell you that the `id` field types in `UserSummary` and `UserDetail` are different.

## 3. Entity-First Architecture

### 3.1 Core Concept

```
┌─────────────────────────────────────┐
│   API Layer (Response)              │  ← API contracts, externally exposed
│   - Select fields from Entity        │
│   - Define API-specific computed fields│
├─────────────────────────────────────┤
│   Domain Layer (Entity)             │  ← Business concepts, relationship definitions
│   - Define business entities         │
│   - Define entity relationships (ERD)│
│   - Independent of specific implementation│
├─────────────────────────────────────┤
│   Data Layer (Repository)           │  ← Data access, encapsulate persistence details
│   - ORM / RPC / Cache / HTTP API    │
│   - Unified interface through Repository│
└─────────────────────────────────────┘
```

**Repository pattern** is the core abstraction of the data layer. It encapsulates all persistence details—whether using ORM to query databases, calling RPC services, reading caches, or accessing external APIs—unified exposure as simple method interfaces (such as `get_by_id`, `get_by_ids`, `find_all`). The domain layer (Entity) obtains data through Repository without needing to care where the data specifically comes from or how it's loaded.

### 3.2 Advantages and Challenges

#### Core Advantages of Entity-First

**Stability and evolvability** are the most significant advantages of Entity-First architecture. By establishing an independent business entity layer, the system gains a stable core. When database structure needs optimization (e.g., splitting large tables, adjusting indexes, migrating to new databases), only need to modify the data layer's Repository implementation, domain models and API contracts are completely unaffected. When business requirement changes cause API contracts to need adjustment, only need to modify Response definition, data layer and domain models remain unchanged. When business logic evolution needs new entity relationships, only need to update ERD definition, existing data access logic can remain stable. This three-layer separation gives the system true continuous evolution capability.

**Clear business semantics** is another important advantage. In Entity-First architecture, we use business language to define the system, not database terminology. `TaskEntity` has business relationships like `owner` and `reporter`, rather than exposing database foreign keys like `owner_id` and `reporter_id`. Frontend developers don't need to understand database design, only need to understand business concepts. New team members can quickly understand business models by reading Entity definitions, without needing to first study complex table structures and foreign key relationships.

**Unified abstraction for multiple data sources** makes complex system development simple. User information might come from PostgreSQL, order data might come from MongoDB, recommendation lists might be read from Redis cache, inventory status might be obtained through RPC calls. In Entity-First architecture, these differences are all shielded by the data access layer. Entity only needs to declare "what data I need", not needing to care "where data comes from". When a data source needs migration or upgrade (e.g., migrating user service from database to microservice), only need to modify the corresponding Repository, Entity and Response don't need any changes.

#### Core Challenge: The Gap Between Data Association and Business Composition

**Problem 1: Blurred Responsibility Boundaries of Repository**

Entity-First architecture introduces an independent business entity layer and Repository pattern, which indeed solves many problems. But in actual development, a fundamental problem quickly emerges: what should Repository be responsible for?

The most intuitive understanding is that Repository is responsible for data access—methods like `get_by_id`, `find_all`, `batch_get`. When an API needs to return a response containing associated data, such as "task list needs to include owner information", the problem arises: where should this assembly logic be placed?

**Option 1: Place in Repository**
```python
class TaskRepository:
    async def get_tasks_with_owners(self):
        # Repository responsible for loading associated data
        tasks = await self.get_tasks()
        user_ids = [t.owner_id for t in tasks]
        users = await user_repo.get_by_ids(user_ids)
        # manually assemble...
        return tasks_with_owners
```
Problem: Repository becomes bloated, responsibilities mixed. Each different use case needs a specific method—`get_tasks_with_owners`, `get_tasks_with_projects`, `get_tasks_with_owners_and_projects`... Repository becomes a dumping ground for use cases.

**Option 2: Place in Service layer**
```python
class TaskService:
    async def get_task_list_with_users(self):
        # Service responsible for assembling data
        tasks = await task_repo.get_tasks()
        users = await user_repo.get_by_ids([t.owner_id for t in tasks])
        # manually assemble...
        return assembled_tasks
```
Problem: Service layer is filled with data assembly code. This code is repetitive, error-prone, difficult to maintain, and mixed with business logic.

Whichever option is chosen, the core problem exists: **data assembly logic has no suitable place to be placed**. Repository should only be responsible for data access, Service should only be responsible for business logic, Response should only be responsible for data structure definition. But in Entity-First architecture, when needing to obtain data from multiple Repositories and combine into a response, where should this logic be placed? Traditional three-layer architecture doesn't give a clear answer.

---

**Summary: The Missing Piece of Entity-First Architecture**

Entity-First architecture provides a clear theoretical framework—independent business entity layer, Repository pattern, deriving Response from Entity. But in actual implementation, it lacks a key execution layer to handle **data assembly logic**: when needing to obtain data from multiple Repositories and combine into a response, where should this logic be placed?

If this problem is not solved, Entity-First architecture will face a dilemma in practice:
- Let Repository bear data assembly responsibility → Repository becomes bloated, becomes a dumping ground for use cases
- Let Service bear data assembly responsibility → Service layer is filled with repetitive, error-prone data assembly code
- Let Response bear data assembly responsibility → Each Response must implement itself, batch loading, N+1 queries, error handling and other problems all need manual solution

This is exactly the problem that pydantic-resolve tries to solve—it provides the missing data assembly execution layer in Entity-First architecture.

### 3.3 Implementation Approach

#### Step 1: Define Business Entities (Entity)
```python
from pydantic import BaseModel
from pydantic_resolve import base_entity, Relationship

# 1. Create Entity base class
BaseEntity = base_entity()

# 2. Define business entities (not dependent on ORM)
class UserEntity(BaseModel):
    """User entity: express business concepts"""
    id: int
    name: str
    email: str

class TaskEntity(BaseModel, BaseEntity):
    """Task entity: define business relationships"""
    __relationships__ = [
        Relationship(
            field='owner_id',
            target_kls=UserEntity,
            loader=user_loader  # don't care where it loads from
        )
    ]
    id: int
    name: str
    owner_id: int
    estimate: int
```

**Key points**:
- Entity is business concept, not bound to specific implementation
- Relationships connected through loader, not DB foreign keys
- Can express cross-data-source relationships

#### Step 2: Define Data Loaders (Loader)
```python
# Loader can connect arbitrary data sources
async def user_loader(user_ids: list[int]):
    # Load from ORM
    users = await UserORM.filter(UserORM.id.in_(user_ids))
    return build_list(users, user_ids, lambda u: u.id)

# Or load from RPC
async def user_loader_from_rpc(user_ids: list[int]):
    users = await user_rpc.batch_get_users(user_ids)
    return build_list(users, user_ids, lambda u: u['id'])

# Or load from Redis
async def user_loader_from_cache(user_ids: list[int]):
    users = await redis.mget(f"user:{uid}" for uid in user_ids)
    return build_list(users, user_ids, lambda u: u['id'])
```

**Key points**:
- Loader shields data source differences
- Entity doesn't care where data comes from
- Can easily switch or combine data sources

#### Step 3: Define API Response from Entity
```python
from pydantic_resolve import DefineSubset, LoadBy, SubsetConfig

# Scenario 1: User summary
class UserSummary(DefineSubset):
    __subset__ = (UserEntity, ('id', 'name'))

# Scenario 2: Task list (including owner)
class TaskResponse(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'name', 'estimate'))

    # Automatically resolve owner, no need to write resolve method
    owner: Annotated[Optional[UserSummary], LoadBy('owner_id')] = None

# Scenario 3: Task detail (including more fields)
class TaskDetailResponse(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'name', 'estimate', 'created_at'))

    owner: Annotated[Optional[UserDetail], LoadBy('owner_id')] = None
```

**Key points**:
- Response derived from Entity, type-safe
- Automatically inherit Entity's relationship definitions
- Can reuse and compose different field subsets
- When Entity changes, Response automatically syncs

### 3.3 Architectural Advantages

#### Advantage 1: Clear Layering
- **Entity** → Domain layer, express business concepts
- **Response** → API layer, define external contracts
- **Loader** → Data layer, handle implementation details

#### Advantage 2: Independent Evolution
- DB structure change → Only need to modify Loader
- API contract change → Only need to modify Response
- Business logic change → Modify Entity and relationships

#### Advantage 3: Unified Type System
```python
# Entity as "single source of truth"
# All Response derived from it, ensuring type consistency

class UserSummary(DefineSubset):
    __subset__ = (UserEntity, ('id', 'name'))

class UserDetail(DefineSubset):
    __subset__ = (UserEntity, ('id', 'name', 'email'))

# Type-safe: id field is int in all Response
```

#### Advantage 4: Native Support for Multiple Data Sources
```python
# Can easily combine relationships from different data sources
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(
            field='owner_id',
            target_kls=UserEntity,
            loader=user_from_db_loader  # Load from DB
        ),
        Relationship(
            field='project_id',
            target_kls=ProjectEntity,
            loader=project_from_rpc_loader  # Load from RPC
        ),
        Relationship(
            field='status_id',
            target_kls=StatusEntity,
            loader=status_from_cache_loader  # Load from cache
        ),
    ]
```

#### Advantage 5: Automatic Data Assembly, Farewell to Verbose Code

**Comparison: Traditional approach vs pydantic-resolve**

**Traditional approach** (5 steps, ~30 lines of code):
```python
async def get_posts_with_users(session: AsyncSession):
    # 1. Query posts
    posts_result = await session.execute(select(Post))
    posts = posts_result.scalars().all()

    # 2. Collect all user_id
    user_ids = list(set([post.user_id for post in posts]))

    # 3. Batch query users
    users_result = await session.execute(
        select(User).where(User.id.in_(user_ids))
    )
    users = users_result.scalars().all()

    # 4. Build user_id -> user mapping
    user_map = {user.id: user for user in users}

    # 5. Manually assemble response
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

**pydantic-resolve approach** (declarative, ~10 lines of code):
```python
# 1. Define Loader
async def user_batch_loader(user_ids: list[int]):
    async with get_db_session() as session:
        result = await session.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users = result.scalars().all()
        return build_list(users, user_ids, lambda u: u.id)

# 2. Define Response (declare how to get associated data)
class PostResponse(BaseModel):
    id: int
    title: str
    user_id: int

    user: Optional[UserResponse] = None
    def resolve_user(self, loader=Loader(user_batch_loader)):
        return loader.load(self.user_id)

# 3. Use Resolver to automatically assemble
@router.get("/posts", response_model=List[PostResponse])
async def get_posts():
    posts = await query_posts_from_db()
    return await Resolver().resolve(posts)
```

**Comparison results**:
| Dimension | Traditional approach | pydantic-resolve |
|-----------|---------------------|------------------|
| Lines of code | ~30 lines | ~10 lines |
| Manual batching | ✗ Need manual implementation | ✓ Automatic batching |
| Error-prone | ✗ Manual mapping | ✓ Framework guaranteed |
| Reusable | ✗ Repeat everywhere | ✓ Loader reusable |
| N+1 risk | ✗ Easy to forget batching | ✓ Automatically avoid |
| Separation of concerns | ✗ Data assembly scattered | ✓ Clear layering |

**Key differences**:
- **Traditional approach**: Imperative, focuses on "how to do" (how to query, how to map, how to assemble)
- **pydantic-resolve**: Declarative, focuses on "what to want" (what associated data is needed)

**More complex scenarios**:

When there are multiple levels of nesting, the code complexity of traditional approach grows exponentially:

```python
# Traditional approach: Get Sprints → Stories → Tasks → Owners (4 levels of nesting)
async def get_sprints_with_full_detail(session):
    # Need 4 levels of loops, each loop needs to:
    # 1. Query current level data
    # 2. Collect next level IDs
    # 3. Batch query next level data
    # 4. Build mapping
    # 5. Manually assemble
    # Code will exceed 100 lines, difficult to maintain
```

```python
# pydantic-resolve: Same requirement
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

# Use
sprints = await query_sprints_from_db()
result = await Resolver().resolve(sprints)
```

**Code volume comparison**:
- Traditional approach: 100+ lines, difficult to maintain
- pydantic-resolve: 30 lines, clear and readable

## 4. Practical Case: Refactoring Existing Projects

### 4.1 Before Refactoring (ORM-First)
```python
# models/task.py (ORM)
from sqlalchemy.orm import relationship

class TaskORM(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    owner_id = Column(Integer, ForeignKey('users.id'))
    project_id = Column(Integer, ForeignKey('projects.id'))

    # Define relationship for loading associated data
    owner = relationship("UserORM", back_populates="tasks")
    project = relationship("ProjectORM", back_populates="tasks")

# schemas/task.py (copy from ORM)
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

# routes/task.py
from sqlalchemy.orm import selectinload

@router.get("/tasks", response_model=List[TaskResponse])
async def get_tasks(session: AsyncSession = Depends(get_session)):
    # Must specify loading strategy, otherwise will produce N+1 queries
    result = await session.execute(
        select(TaskORM)
        .options(
            selectinload(TaskORM.owner),      # Eager load owner
            selectinload(TaskORM.project)     # Eager load project
        )
    )
    tasks = result.scalars().all()
    return [TaskResponse.model_validate(t) for t in tasks]
```

### 4.2 After Refactoring (Entity-First)
```python
# entities/task.py (business entity)
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(field='owner_id', target_kls=UserEntity, loader=user_loader),
        Relationship(field='project_id', target_kls=ProjectEntity, loader=project_loader),
    ]
    id: int
    name: str
    owner_id: int
    project_id: int

# responses/task.py (API contract)
class TaskResponse(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'name', 'owner_id', 'project_id'))

    owner: Annotated[Optional[UserResponse], LoadBy('owner_id')] = None
    project: Annotated[Optional[ProjectSummary], LoadBy('project_id')] = None

# routes/task.py
@router.get("/tasks", response_model=List[TaskResponse])
async def get_tasks():
    tasks_orm = await query_tasks_from_db()
    # 1. Convert ORM objects to Response objects
    tasks = [TaskResponse.model_validate(t) for t in tasks_orm]
    # 2. Resolver automatically resolves associated data
    return await Resolver().resolve(tasks)
```

**Key advantage: Assembly process completely shields database details, reduces cognitive burden**

Compared to 4.1, Entity-First approach in the entire data assembly process **completely doesn't need to perceive the database**:

- ❌ No need to import SQLAlchemy modules like `selectinload`, `relationship`
- ❌ No need to think about loading strategies (will it N+1? use selectinload or joinedload?)
- ❌ No need to manually write loop assembly code

Only need to declare business semantics: "this task needs an owner" → `LoadBy('owner_id')`. Batch queries, mapping building, performance optimization at the database level are all automatically handled by `Resolver`.

### 4.3 Comparison Analysis

| Dimension | ORM-First | Entity-First |
|-----------|-----------|--------------|
| Type definition scattered | ORM and Schema duplicated definitions | Entity as single source |
| Relationship definition | Each Response repeats writing resolve | ERD unified definition, automatic reuse |
| Data source switching | Need to modify multiple places | Only need to modify Loader |
| Field subsets | Manual copy-paste | DefineSubset automatic generation |
| Cross-data sources | Difficult to unify | Loader unified interface |
| Test friendliness | Dependent on DB | Can mock Loader |
| Implementation detail exposure | Route layer exposes DB fields (foreign key IDs) and loading strategies (selectinload) | Route layer only declares business semantics, shields DB details |

## 5. How to Migrate to Entity-First Architecture

### 5.1 Migration Steps

#### Step 1: Extract Entity
```python
# Extract business concepts from existing ORM models
class UserEntity(BaseModel):
    # Only keep business fields, remove DB-specific fields
    id: int
    name: str
    email: str
    # Remove: password_hash, created_at, updated_at
```

#### Step 2: Define ERD
```python
# Centrally define entity relationships
class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(field='owner_id', target_kls=UserEntity, loader=user_loader),
    ]
```

#### Step 3: Refactor Response
```python
# Derive from Entity, not from ORM
class TaskResponse(DefineSubset):
    __subset__ = (TaskEntity, ('id', 'name'))
    owner: Annotated[Optional[UserSummary], LoadBy('owner_id')] = None
```

#### Step 4: Gradual Replacement
- Keep existing ORM
- New features use Entity-First
- Old interfaces gradually refactored

### 5.2 Precautions
- Don't refactor all code at once
- ORM and Entity can coexist
- Prioritize using Entity-First in new features
- Old code can be gradually migrated during maintenance

## 6. Frequently Asked Questions (FAQ)

### Q1: Isn't Entity just a copy of ORM?
**A**: No, Entity and ORM are fundamentally different:
- Entity is business concept, ORM is DB mapping
- Entity can express relationships that DB cannot express (cross-data sources)
- Entity can contain computed fields, ORM typically doesn't
- Entity is stable core, ORM is replaceable implementation

### Q2: Won't this increase code volume?
**A**: Initially it might increase, but long-term benefits are greater:
- Eliminates duplicate code between ORM and Schema
- DefineSubset automatically generates Response, reducing manual maintenance
- Loaders can be reused, reducing repetitive logic for data access

### Q3: Do small projects need this?
**A**: Depends on project complexity:
- Simple CRUD projects: ORM-First is sufficient
- Has complex business logic: Recommend Entity-First
- Multiple data sources: Strongly recommend Entity-First
- Team collaboration: Entity-First is easier to maintain

### Q4: How to handle write operations (POST/PUT/PATCH)?
**A**: Write operations differ from read operations:
- Write operations: Can still use ORM or Pydantic schema as DTO
- Read operations: Use Entity-First to gain architectural advantages
- Or: Define dedicated CreateDTO/UpdateDTO, derived from Entity

## 7. Summary

### 7.1 Core Arguments

The core argument of this article is: Pydantic schemas shouldn't be shadows of ORM, but should be built on an independent business entity layer. This means we need to establish an independent business entity layer to express pure domain concepts, decouple data sources from business logic through the Loader mechanism, and finally derive API Response from Entity. This architectural transformation is not just an adjustment of code organization, but a rethinking of the system's essence—making business concepts the core of architecture, rather than being bound by database structure.

### 7.2 Architectural Principles

Entity-First architecture follows four core principles: First is clear layering, the system is divided into API layer (external contracts), Domain layer (business entities), Data layer (data access); Second is unidirectional dependency, upper layers depend on lower layers, but lower layers don't depend on upper layers, ensuring independence of each layer; Third is independent evolution, each layer can be independently modified without affecting other layers, optimization of database structure won't spread to business logic and API contracts; Finally is type safety, through Entity unified type definitions, ensuring type consistency throughout the system.

### 7.3 The Role of pydantic-resolve

pydantic-resolve provides complete tool support for Entity-First architecture. It uniformly manages entity relationships through ERD (Entity Relationship Diagram), automatically optimizes data access through DataLoader pattern to avoid N+1 queries, implements type definition reuse and composition through DefineSubset mechanism. More importantly, it provides an automatic data assembly execution layer, allowing developers to only declare "what data is needed", without caring about "how to obtain and assemble data", significantly reducing development cognitive burden.

### 7.4 Call to Action

I hope the FastAPI community can rethink the way Pydantic is used, shifting from the widely used "ORM-First" to a clearer "Entity-First" architecture. This is not just an adjustment of technical choice, but an upgrade of architectural philosophy—building systems on stable business concepts, rather than volatile database structures. In the long run, this architecture can significantly improve system maintainability, evolvability, and team collaboration efficiency.

## 8. Additional Topics

### 8.1 How Many Problems Can SQLModel Solve?

SQLModel is a library that attempts to unify SQLAlchemy and Pydantic, allowing one class to serve as both a database model and Pydantic schema. This is a practical tool, but can it solve the architectural problems discussed in this article? Let's analyze objectively.

#### Problems SQLModel Can Solve

**Type definition duplication**: SQLModel does solve the most obvious problem—no need to define the same fields repeatedly in ORM models and Pydantic schemas. A single `class User(SQLModel, table=True)` definition serves as both database table structure and data validation and serialization. When modifying fields, only need to change one place, avoiding the risk of inconsistency.

**Field synchronization problem**: Since there's only a single definition source, field names, types, default values, etc. naturally stay consistent, avoiding situations where ORM and Schema fields don't match.

#### Core Problems SQLModel Cannot Solve

**Essence of schemas passively following ORM unchanged**: SQLModel's core design philosophy is still "ORM-first". It makes Pydantic schemas an alias of database models, rather than establishing an independent business entity layer. Database design still directly determines the structure of API contracts, and business concepts are still bound by database table structure.

**Lack of independent business abstraction layer**: When using SQLModel, `class User` expresses "users table", not "user business concept". If database design merges `owner_id` and `reporter_id` into a single field, API contracts must also change accordingly. SQLModel doesn't provide a layer to express stable business concepts, separated from volatile technical implementations.

**Missing unified multi-data source handling capability**: SQLModel can only handle data sources connected by SQLAlchemy. When projects need to combine data from multiple data sources like databases, RPC services, Redis cache, external APIs, SQLModel is powerless. It doesn't provide a unified abstraction layer to handle data sources in different formats.

**Data assembly dilemma still exists**: For scenarios not using SQLAlchemy `relationship`, SQLModel doesn't provide a better solution. Developers still need to manually write code for querying, batch loading, building mappings, and assembling data, facing exactly the same N+1 query risks and code duplication problems.

**Missing schema reuse and composition mechanism**: In actual projects, the same entity often needs different views (e.g., user list only needs ID and name, user detail needs complete information). SQLModel doesn't provide a mechanism to derive field subsets from models, developers either copy definitions or manually select fields, returning to the old problems of type duplication and maintenance difficulties.

#### SQLModel's Positioning

SQLModel is a practical tool that optimizes development experience within the ORM-First framework, but it doesn't solve fundamental problems at the architectural level. More precisely, SQLModel is "a better ORM-First solution", not an Entity-First solution.

**Scenarios suitable for using SQLModel**: Simple CRUD projects, single data source, small projects where API contracts can follow database structure changes. In these scenarios, SQLModel can reduce boilerplate code and improve development efficiency.

**Scenarios not suitable for using SQLModel**: Complex business logic, long-term projects needing stable API contracts, systems with multi-data source integration, team collaboration projects needing clear layered architecture. In these scenarios, the independent business entity layer, unified type system, and flexible data loading mechanism provided by Entity-First architecture (with pydantic-resolve) are the right choices for sustainable development.

---

### 8.2 Relationship Between Entity-First and Clean Architecture

Entity-First architecture has a natural fit with Clean Architecture. We can map the three core levels of Entity-First to the classic layers of Clean Architecture, thereby more clearly understanding its architectural advantages.

#### Layer Correspondence

```
Clean Architecture          Entity-First Architecture
┌─────────────────┐        ┌──────────────────────────┐
│  Frameworks &   │        │   API Layer (Response)    │ ← External interface
│  Interfaces     │        │   - FastAPI routes        │
├─────────────────┤        ├──────────────────────────┤
│  Application    │ ←──→   │   Resolver (Execution)    │ ← Use case orchestration
│  Business Rules │        │   - Data assembly logic   │
├─────────────────┤        ├──────────────────────────┤
│  Enterprise     │ ←──→   │   Domain Layer (Entity)   │ ← Business rules
│  Business Rules │        │   - Business entity defs  │
│  (Entities)     │        │   - ERD relationship decl │
├─────────────────┤        ├──────────────────────────┤
│  DB, Web, GUI   │        │   Data Layer (Loader)     │ ← Data access
│  (Adapters)     │        │   - Repository impl       │
└─────────────────┘        └──────────────────────────┘
```

#### Core Concept Mapping

**1. Entity (Domain Entity) - Complete Correspondence**

The Entity layer in Clean Architecture contains enterprise-level business rules and is the most stable, highest-level part of the system. Entity in Entity-First plays the exact same role: expressing pure business concepts (such as User, Task, Project), independent of any framework, database, or UI technology.

Both emphasize: business concepts should become the core of architecture, rather than being bound by technical implementation details.

**2. Use Case (Application Business Rules) and Resolver - Automated Orchestration**

Use Cases in Clean Architecture contain application-specific business rules, responsible for orchestrating Entity interactions to complete specific use cases. In the "get task list" use case, Use Case needs to coordinate data loading for Task, User, Project.

`Resolver` in Entity-First plays the same role, but with a key difference: it automates the common patterns of data assembly. In Clean Architecture, orchestration logic needs to be handwritten for each use case (query main data, collect IDs, batch load, assemble results), while Entity-First through declarative `LoadBy` annotations and automatic dependency analysis, lets `Resolver` automatically complete this work.

This automation reduces duplicate code, lowers error risk, while maintaining Clean Architecture's core philosophy: use case orchestration is independent of specific implementation.

**3. Adapter (Interface Adapter) and Loader - Unified Abstraction**

Adapter in Clean Architecture is responsible for converting external world data formats into internally usable Entities. Whether data comes from PostgreSQL, RPC services, Redis cache, or external APIs, Adapter uniformly converts them into domain entities.

`Loader` in Entity-First plays the exact same role. Each Loader is an adapter that shields data source implementation details, only exposing the unified interface of "return entity list based on ID list". This abstraction makes data source migration, replacement, or combination exceptionally simple—only need to modify Loader implementation, without affecting upper-level business logic.

#### Architectural Advantages

**1. Correct Dependency Direction (Dependency Inversion Principle)**

The core principle of Clean Architecture is "dependency direction points inward", and Entity-First fully complies with this principle:

- **Entity doesn't depend on any framework or database** - It's the innermost stable core
- **API layer depends on Entity** - But Entity is completely unaware of API's existence
- **Loader/Adapter implementations can be freely replaced** - Upper-level code is completely unaffected

This dependency inversion ensures system evolvability: when database structure changes, external services migrate, caching strategies adjust, only need to modify corresponding data access layer, business logic and API contracts remain stable.

**2. Separation of Business Logic and Technical Implementation**

Entity-First architecture clearly separates three levels:

- **Entity expresses "what is"** - What attributes users have, tasks have owners, these are business concepts
- **Loader solves "how to do"** - Where data comes from, how to batch query, how to avoid N+1
- **Response defines "what to expose"** - What fields API returns, how to combine, how to customize for specific use cases

This separation allows developers to think in business language, rather than being constantly interrupted by technical details. When business requirements change, modifications are often confined to one layer, not affecting everything.

**3. Testability**

Clean Architecture emphasizes testability because business logic is completely decoupled from external dependencies. Entity-First inherits this advantage:

Since Loader is a unified data access interface, tests can easily Mock Loader to provide predefined test data. Test cases focus on verifying business logic (e.g., whether the relationship between tasks and owners is correct), without needing to start databases, prepare test data, manage transaction state. This makes unit tests run fast, stable, and easy to maintain.

**4. Evolution Capability**

The ultimate goal of Clean Architecture is to give systems long-term evolution capability. Entity-First excels in this regard:

| Evolution scenario | Clean Architecture response | Entity-First implementation |
|-------------------|-----------------------------|---------------------------|
| Database migration | Only need to modify Adapter | Only need to modify Loader |
| API upgrade | Only need to modify Interface/Presenter | Only need to modify Response |
| Business expansion | Expand Entity and Use Case | Expand Entity and ERD |
| Multi-data source integration | Add new Adapter | Add new Loader |

This architecture keeps the system clear, controllable, and understandable during business growth, technology upgrades, and team expansion. In the long run, this is a more important return on investment than short-term development efficiency.

#### Summary

Entity-First architecture is a natural implementation of Clean Architecture in the FastAPI + Pydantic ecosystem. It's not a new concept created out of thin air, but combines Clean Architecture's classic principles with modern Python technology stack, providing a set of actionable practical solutions:

- **Entity layer** corresponds to Enterprise Business Rules, expressing stable business concepts
- **Resolver layer** corresponds to Use Cases, automated data assembly orchestration
- **Loader layer** corresponds to Adapters, isolating external data source implementation details

Adopting Entity-First architecture means your project is built on proven architectural principles from the start, laying a solid foundation for long-term system evolution.
