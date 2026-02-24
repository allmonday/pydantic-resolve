# GraphQL Demo

这是一个演示 pydantic-resolve GraphQL 功能的 FastAPI 应用。

## 前置要求

确保已安装项目依赖：

```bash
# 在项目根目录安装依赖
uv pip install -e ".[dev]"
# 或
pip install -e ".[dev]"
```

## 启动服务器

**重要**: 必须使用项目的虚拟环境，不要使用系统 Python。

```bash
# 方式 1: 使用 uv（推荐）
uv run uvicorn demo.graphql.app:app --reload

# 方式 2: 使用 Python 模块运行
uv run python -m demo.graphql.app

# 方式 3: 使用 Makefile
cd demo/graphql
make run

# 方式 4: 使用启动脚本
./demo/graphql/run.sh
```

服务器将在 `http://localhost:8000` 启动。

## 查询示例

### 1. 获取所有用户

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ users { id name email role } }"}'
```

### 2. 获取分页用户

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ users(limit: 2, offset: 1) { id name email } }"}'
```

### 3. 获取单个用户

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ user(id: 1) { id name email role } }"}'
```

### 4. 获取用户及其文章（嵌套查询）

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ user(id: 1) { id name email posts { title content status } } }"}'
```

### 5. 获取所有文章

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ posts { id title content status } }"}'
```

### 6. 获取已发布的文章

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ posts(status: \"published\") { id title content } }"}'
```

### 7. 获取文章及其作者（多层级嵌套）

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ posts { title content author { name email role } } }"}'
```

### 8. 获取评论及作者和文章（三层嵌套）

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ comments { text author { name email } post { title author { name } } } }"}'
```

### 9. 获取所有管理员

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ admins { id name email } }"}'
```

### 10. 获取单个文章

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ post(id: 1) { title content author { name email } comments { text author { name } } } }"}'
```

## 获取 GraphQL Schema

```bash
curl http://localhost:8000/schema
```

## API 文档

访问 `http://localhost:8000/docs` 查看 FastAPI 自动生成的交互式文档。

## 使用 GraphiQL 或 Apollo Explorer

服务器已启用 CORS 支持，可以在以下在线 GraphQL IDE 中使用：

### 推荐工具

1. **GraphiQL Online**: https://graphqlbin.com/graphiql
   - Endpoint: `http://localhost:8000/graphql`
   - Schema URL: `http://localhost:8000/schema`

2. **Apollo Explorer**: https://explorer.apollographql.com/
   - GraphQL Endpoint: `http://localhost:8000/graphql`

3. **Altair GraphQL Client**: https://altair.sirmuel.design/
   - 支持浏览器扩展和桌面应用

### 浏览器插件

- **Chrome**: GraphQL Playground Extension
- **Firefox**: GraphQL Network Inspector
- **Safari**: Altair GraphQL Client

### 配置示例

在 GraphiQL 中：
```
GraphQL Endpoint: http://localhost:8000/graphql
Headers (可选):
  Content-Type: application/json
```

然后在 Query 面板中输入查询：
```graphql
query {
  users {
    id
    name
    email
    posts {
      title
    }
  }
}
```

## 数据结构

### User
- `id`: 用户 ID
- `name`: 用户名
- `email`: 邮箱
- `role`: 角色 (admin/user)
- `posts`: 该用户的文章列表

### Post
- `id`: 文章 ID
- `title`: 标题
- `content`: 内容
- `author_id`: 作者 ID
- `status`: 状态 (published/draft)
- `author`: 作者信息
- `comments`: 评论列表

### Comment
- `id`: 评论 ID
- `text`: 评论内容
- `author_id`: 作者 ID
- `post_id`: 文章 ID
- `author`: 作者信息
- `post`: 文章信息

## 可用的根查询

- `users(limit: Int, offset: Int)`: [User] - 获取用户列表
- `user(id: Int!)`: User - 获取单个用户
- `admins`: [User] - 获取所有管理员
- `posts(limit: Int, status: String)`: [Post] - 获取文章列表
- `post(id: Int!)`: Post - 获取单个文章
- `comments`: [Comment] - 获取所有评论

### 多查询支持

支持在单个请求中执行多个根查询：

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ posts { id title } users { id name } }"}'
```

**注意**：GraphQL 规范要求同一级别的字段名必须唯一。如果需要查询同一类型的多个数据，请使用不同的根查询名称。
