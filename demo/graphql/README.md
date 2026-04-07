# GraphQL Demo

基于 SQLAlchemy ORM + `build_relationship` 的 GraphQL Demo，演示 pydantic-resolve 的以下能力：

- 从 ORM 自动发现关联关系并生成 DataLoader
- 从 ERD 自动生成 GraphQL Schema
- 支持 Query 和 Mutation

## 前置要求

```bash
# 在项目根目录安装依赖
uv pip install -e ".[dev]"
```

## 启动服务器

```bash
uv run uvicorn demo.graphql.app:app --reload
```

服务器将在 `http://localhost:8000` 启动。

## 配置流程

本 Demo 的核心是 `entities_v3.py`，通过四个步骤完成 GraphQL 的配置：

### Step 1: 定义 DTO 和 ORM 模型

DTO 是独立的 API 契约，ORM 模型描述数据库结构：

```python
# DTO - 定义 API 契约
class UserEntityV3(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    role: str
    created_at: datetime

# ORM - 定义数据库结构
class UserOrm(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    # ...
    posts: Mapped[List["PostOrm"]] = relationship(back_populates="author")
```

### Step 2: 通过 `build_relationship` 自动发现关联关系

将 DTO 映射到 ORM 模型，框架自动读取 ORM 元数据生成 DataLoader：

```python
from pydantic_resolve.integration.sqlalchemy import build_relationship
from pydantic_resolve.integration.mapping import Mapping

relationship_entities = build_relationship(
    mappings=[
        Mapping(entity=UserEntityV3, orm=UserOrm),
        Mapping(entity=PostEntityV3, orm=PostOrm),
        Mapping(entity=CommentEntityV3, orm=CommentOrm),
    ],
    session_factory=session_factory,
)
```

ORM 中已定义的关系会被自动识别：

```
User ──1:N──> Post       (user.posts)
Post ──N:1──> User       (post.author)
User ──1:N──> Comment    (user.comments)
Post ──1:N──> Comment    (post.comments)
Comment ──N:1──> User    (comment.author)
Comment ──N:1──> Post    (comment.post)
```

### Step 3: 通过 `Entity` + `QueryConfig` / `MutationConfig` 注册查询和变更

为每个 DTO 配置 GraphQL 的入口方法：

```python
from pydantic_resolve import Entity, QueryConfig, MutationConfig

qm_entities = [
    Entity(
        kls=UserEntityV3,
        queries=[
            QueryConfig(method=get_all_users, name="users_v3"),
            QueryConfig(method=get_user_by_id, name="user_v3"),
        ],
        mutations=[
            MutationConfig(method=create_user, name="createUserV3"),
        ],
    ),
    Entity(
        kls=PostEntityV3,
        queries=[
            QueryConfig(method=get_all_posts, name="posts_v3"),
            QueryConfig(method=get_post_by_id, name="post_v3"),
        ],
        mutations=[
            MutationConfig(method=create_post, name="createPostV3"),
        ],
    ),
    # ... CommentEntityV3 同理
]
```

查询和变更方法的签名决定了 GraphQL 的参数类型，返回类型由 DTO 定义：

```python
# 参数 (limit, offset) 自动映射为 GraphQL 参数
# 返回 List[UserEntityV3] 自动映射为 GraphQL 类型
async def get_all_users(limit: int = 10, offset: int = 0) -> List[UserEntityV3]:
    ...
```

### Step 4: 合并为 ErDiagram 并配置 Resolver

将 Query/Mutation 配置和自动发现的关系合并，生成完整的 ER Diagram：

```python
from pydantic_resolve import ErDiagram, config_global_resolver

# Q/M 配置为基础，追加自动发现的关系
diagram_v3 = ErDiagram(entities=qm_entities).add_relationship(relationship_entities)

# 配置全局 Resolver
config_global_resolver(diagram_v3)
```

`ErDiagram` 会自动生成 GraphQL Schema，包括：
- 每个 Entity 对应一个 GraphQL Type
- `QueryConfig` 注册为 Query 入口
- `MutationConfig` 注册为 Mutation 入口
- 关联关系自动生成为嵌套查询字段

### 在 FastAPI 中使用

`app.py` 中通过 `GraphQLHandler` 执行查询：

```python
from pydantic_resolve import GraphQLHandler, SchemaBuilder

handler = GraphQLHandler(diagram, enable_from_attribute_in_type_adapter=True)
schema_builder = SchemaBuilder(diagram)

@app.post("/graphql")
async def graphql_endpoint(req: GraphQLRequest):
    return await handler.execute(query=req.query)
```

## Endpoints

| Endpoint | Method | 说明 |
|----------|--------|------|
| `/graphql` | GET | GraphiQL Playground（浏览器直接访问） |
| `/graphql` | POST | GraphQL 查询端点 |
| `/schema` | GET | SDL 格式的 GraphQL Schema |
| `/docs` | GET | FastAPI 交互式文档 |

## 查询示例

### 1. 获取所有用户

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ userEntityV3UsersV3 { id name email role created_at } }"}'
```

### 2. 获取分页用户

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ userEntityV3UsersV3(limit: 2, offset: 1) { id name email } }"}'
```

### 3. 获取单个用户及其文章（嵌套查询）

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ userEntityV3UserV3(id: 1) { id name email posts { title content status } } }"}'
```

### 4. 获取所有文章

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ postEntityV3PostsV3 { id title content status created_at } }"}'
```

### 5. 按状态筛选文章

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ postEntityV3PostsV3(status: \"published\") { id title content } }"}'
```

### 6. 获取文章及作者（多层级嵌套）

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ postEntityV3PostsV3 { title content author { name email role } } }"}'
```

### 7. 获取评论及作者和文章（三层嵌套）

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ commentEntityV3CommentsV3 { text author { name email } post { title author { name } } } }"}'
```

### 8. 获取单个文章及评论

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ postEntityV3PostV3(id: 1) { title content author { name email } comments { text author { name } } } }"}'
```

### 9. 多查询

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ postEntityV3PostsV3 { id title } userEntityV3UsersV3 { id name } }"}'
```

## Mutation 示例

### 创建用户

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { userEntityV3CreateUserV3(name: \"Eve\", email: \"eve@example.com\") { id name email } }"}'
```

### 使用 Input Type 创建用户

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { userEntityV3CreateUserWithInputV3(input: { name: \"Frank\", email: \"frank@example.com\", role: USER }) { id name email role } }"}'
```

### 创建文章

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { postEntityV3CreatePostV3(title: \"New Post\", content: \"Hello\", author_id: 1) { id title status } }"}'
```

### 创建评论

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { commentEntityV3CreateCommentV3(text: \"Nice!\", author_id: 2, post_id: 1) { id text } }"}'
```

## 数据模型

### UserEntityV3
- `id`: Int
- `name`: String
- `email`: String
- `role`: String (admin/user)
- `created_at`: DateTime

### PostEntityV3
- `id`: Int
- `title`: String
- `content`: String
- `author_id`: Int (FK → User)
- `status`: String (published/draft/archived)
- `created_at`: DateTime

### CommentEntityV3
- `id`: Int
- `text`: String
- `author_id`: Int (FK → User)
- `post_id`: Int (FK → Post)
- `created_at`: DateTime

## 可用查询

| 查询 | 参数 | 返回类型 | 说明 |
|------|------|----------|------|
| `userEntityV3UsersV3` | `limit: Int, offset: Int` | [User] | 获取用户列表（分页） |
| `userEntityV3UserV3` | `id: Int!` | User | 获取单个用户 |
| `postEntityV3PostsV3` | `limit: Int, status: String` | [Post] | 获取文章列表（可按状态筛选） |
| `postEntityV3PostV3` | `id: Int!` | Post | 获取单个文章 |
| `commentEntityV3CommentsV3` | - | [Comment] | 获取所有评论 |

## 可用变更

| 变更 | 参数 | 返回类型 | 说明 |
|------|------|----------|------|
| `userEntityV3CreateUserV3` | `name, email, role?` | User | 创建用户 |
| `userEntityV3CreateUserWithInputV3` | `input: CreateUserInput` | User | 使用 Input Type 创建用户 |
| `postEntityV3CreatePostV3` | `title, content, author_id, status?` | Post | 创建文章 |
| `postEntityV3CreatePostWithInputV3` | `input: CreatePostInput` | Post | 使用 Input Type 创建文章 |
| `commentEntityV3CreateCommentV3` | `text, author_id, post_id` | Comment | 创建评论 |

## MCP Server

Demo 包含一个 MCP Server，可将 GraphQL API 暴露给 AI 代理：

```bash
uv run python -m demo.graphql.mcp_server
```
