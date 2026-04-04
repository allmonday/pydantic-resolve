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
  -d '{"query": "{ users_v3 { id name email role created_at } }"}'
```

### 2. 获取分页用户

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ users_v3(limit: 2, offset: 1) { id name email } }"}'
```

### 3. 获取单个用户及其文章（嵌套查询）

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ user_v3(id: 1) { id name email posts_v3 { title content status } } }"}'
```

### 4. 获取所有文章

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ posts_v3 { id title content status created_at } }"}'
```

### 5. 按状态筛选文章

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ posts_v3(status: \"published\") { id title content } }"}'
```

### 6. 获取文章及作者（多层级嵌套）

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ posts_v3 { title content author { name email role } } }"}'
```

### 7. 获取评论及作者和文章（三层嵌套）

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ comments_v3 { text author { name email } post { title author { name } } } }"}'
```

### 8. 获取单个文章及评论

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ post_v3(id: 1) { title content author { name email } comments_v3 { text author { name } } } }"}'
```

### 9. 多查询

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ posts_v3 { id title } users_v3 { id name } }"}'
```

## Mutation 示例

### 创建用户

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { createUserV3(name: \"Eve\", email: \"eve@example.com\") { id name email } }"}'
```

### 使用 Input Type 创建用户

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { createUserWithInputV3(input: { name: \"Frank\", email: \"frank@example.com\", role: user }) { id name email role } }"}'
```

### 创建文章

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { createPostV3(title: \"New Post\", content: \"Hello\", author_id: 1) { id title status } }"}'
```

### 创建评论

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { createCommentV3(text: \"Nice!\", author_id: 2, post_id: 1) { id text } }"}'
```

## 数据模型

本 Demo 使用 SQLAlchemy ORM 定义模型，通过 `build_relationship` 自动发现关联关系：

```
User ──1:N──> Post       (user.posts)
Post ──N:1──> User       (post.author)
User ──1:N──> Comment    (user.comments)
Post ──1:N──> Comment    (post.comments)
Comment ──N:1──> User    (comment.author)
Comment ──N:1──> Post    (comment.post)
```

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
| `users_v3` | `limit: Int, offset: Int` | [User] | 获取用户列表（分页） |
| `user_v3` | `id: Int!` | User | 获取单个用户 |
| `posts_v3` | `limit: Int, status: String` | [Post] | 获取文章列表（可按状态筛选） |
| `post_v3` | `id: Int!` | Post | 获取单个文章 |
| `comments_v3` | - | [Comment] | 获取所有评论 |

## 可用变更

| 变更 | 参数 | 返回类型 | 说明 |
|------|------|----------|------|
| `createUserV3` | `name, email, role?` | User | 创建用户 |
| `createUserWithInputV3` | `input: CreateUserInput` | User | 使用 Input Type 创建用户 |
| `createPostV3` | `title, content, author_id, status?` | Post | 创建文章 |
| `createPostWithInputV3` | `input: CreatePostInput` | Post | 使用 Input Type 创建文章 |
| `createCommentV3` | `text, author_id, post_id` | Comment | 创建评论 |

## MCP Server

Demo 包含一个 MCP Server，可将 GraphQL API 暴露给 AI 代理：

```bash
uv run python -m demo.graphql.mcp_server
```
