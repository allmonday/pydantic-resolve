# GraphQL Demo 目录结构

```
demo/
├── README.md                      # Demo 总览
└── graphql/                       # GraphQL Demo 应用
    ├── __init__.py               # 包初始化文件
    ├── app.py                    # FastAPI 应用入口
    ├── entities.py               # 实体定义 (User, Post, Comment)
    ├── test_demo.py              # Python 测试脚本
    ├── run.sh                    # 服务器启动脚本
    ├── test_queries.sh           # Curl 查询测试脚本
    ├── README.md                 # 详细使用文档
    └── STRUCTURE.md              # 本文件
```

## 文件说明

### app.py
FastAPI 应用主入口，创建 GraphQL 路由并启动服务器。

### entities.py
定义演示用的实体：
- **UserEntity**: 用户实体，包含 id, name, email, role 字段
- **PostEntity**: 文章实体，包含 id, title, content, author_id, status 字段
- **CommentEntity**: 评论实体，包含 id, text, author_id, post_id 字段

每个实体都有 `@query` 装饰的静态方法，暴露为 GraphQL 根查询。

### test_demo.py
Python 测试脚本，运行各种 GraphQL 查询并打印结果。

### run.sh
服务器启动脚本，使用 uvicorn 启动 FastAPI 应用。

### test_queries.sh
Curl 查询测试脚本，运行各种 GraphQL 查询并格式化输出。

## 数据关系

```
User (用户)
  ↓ 1:N
Post (文章)
  ↓ 1:N
Comment (评论)

User (1) ← (N) Post.author_id
Post (1) ← (N) Comment.post_id
User (1) ← (N) Comment.author_id
```

## 可用的 GraphQL 查询

### 查询用户
- `users(limit: Int, offset: Int)` - 获取用户列表
- `user(id: Int!)` - 获取单个用户
- `admins` - 获取所有管理员

### 查询文章
- `posts(limit: Int, status: String)` - 获取文章列表
- `post(id: Int!)` - 获取单个文章

### 查询评论
- `comments` - 获取所有评论

## 嵌套查询示例

```graphql
# 用户及其文章
{
  user(id: 1) {
    id
    name
    posts {
      title
      content
    }
  }
}

# 文章及其作者
{
  posts {
    title
    author {
      name
      email
    }
  }
}

# 评论的作者和文章
{
  comments {
    text
    author {
      name
    }
    post {
      title
    }
  }
}
```
