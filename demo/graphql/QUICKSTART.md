# GraphQL Demo 快速入门

## 前置要求

确保在项目根目录已安装依赖：

```bash
uv pip install -e ".[dev]"
```

## 1 分钟启动

```bash
# 方式 1: 使用 uvicorn（推荐，支持热重载）
uv run uvicorn demo.graphql.app:app --reload

# 方式 2: 使用 Makefile
cd demo/graphql
make run

# 方式 3: 使用启动脚本
./demo/graphql/run.sh
```

服务器将在 `http://localhost:8000` 启动。

## 立即测试

在另一个终端运行：

```bash
# 自动测试脚本
cd demo/graphql
make test-curl
```

或手动测试：

```bash
# 获取所有用户
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ users { id name email role } }"}'
```

## 可用端点

- **GraphQL 查询**: `POST http://localhost:8000/graphql`
- **Schema 查看器**: `GET http://localhost:8000/schema`
- **API 文档**: `GET http://localhost:8000/docs`

## 核心查询示例

### 基础查询
```graphql
{ users { id name email } }
```

### 参数查询
```graphql
{ users(limit: 2) { id name } }
{ user(id: 1) { id name email } }
```

### 嵌套查询
```graphql
{
  user(id: 1) {
    name
    posts {
      title
    }
  }
}
```

### 多层嵌套
```graphql
{
  posts {
    title
    author {
      name
      email
    }
    comments {
      text
      author {
        name
      }
    }
  }
}
```

## 数据模型

### User
```graphql
type User {
  id: Int!
  name: String!
  email: String!
  role: String!
  posts: [Post!]!
}
```

### Post
```graphql
type Post {
  id: Int!
  title: String!
  content: String!
  status: String!
  author: User
  comments: [Comment!]!
}
```

### Comment
```graphql
type Comment {
  id: Int!
  text: String!
  author: User
  post: Post
}
```

## 根查询

```graphql
type Query {
  users(limit: Int, offset: Int): [User!]!
  user(id: Int!): User
  admins: [User!]!
  posts(limit: Int, status: String): [Post!]!
  post(id: Int!): Post
  comments: [Comment!]!
}
```

## 更多帮助

- 查看完整文档: [README.md](./README.md)
- 查看目录结构: [STRUCTURE.md](./STRUCTURE.md)
- 查看 Makefile: `make help`
