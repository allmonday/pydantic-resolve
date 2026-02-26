# GraphQL Mutations 示例

本目录包含了 pydantic-resolve 的 GraphQL mutation 功能的完整示例。

## 已实现的 Mutations

### UserEntity（用户相关）
- **createUser(name, email, role)** - 创建新用户
- **updateUser(id, name?, email?)** - 更新用户信息
- **deleteUser(id)** - 删除用户

### PostEntity（文章相关）
- **createPost(title, content, author_id, status)** - 创建新文章
- **updatePost(id, title?, content?, status?)** - 更新文章内容
- **publishPost(id)** - 发布文章（将状态改为 published）
- **deletePost(id)** - 删除文章

### CommentEntity（评论相关）
- **createComment(text, author_id, post_id)** - 创建新评论
- **updateComment(id, text?)** - 更新评论内容
- **deleteComment(id)** - 删除评论

## 快速开始

### 1. 启动 GraphQL 服务

```bash
cd /Users/tangkikodo/Documents/pydantic-resolve
uv run uvicorn demo.graphql.app:app --reload
```

### 2. 测试 Mutations

#### 创建用户
```graphql
mutation {
  createUser(name: "Alice", email: "alice@example.com", role: "admin") {
    id
    name
    email
    role
  }
}
```

#### 创建用户并请求关联数据
```graphql
mutation {
  createUser(name: "Bob", email: "bob@test.com", role: "user") {
    id
    name
    myposts {
      id
      title
    }
  }
}
```

#### 创建文章
```graphql
mutation {
  createPost(
    title: "My First Post"
    content: "Hello World!"
    author_id: 1
    status: "published"
  ) {
    id
    title
    status
    author {
      id
      name
    }
  }
}
```

#### 创建评论（带完整关联数据）
```graphql
mutation {
  createComment(
    text: "Great article!"
    author_id: 1
    post_id: 1
  ) {
    id
    text
    author {
      id
      name
      email
    }
    post {
      id
      title
      author {
        name
      }
    }
  }
}
```

#### 多个 Mutations 顺序执行
```graphql
mutation {
  user1: createUser(name: "User 1", email: "user1@test.com", role: "user") {
    id
    name
  }
  user2: createUser(name: "User 2", email: "user2@test.com", role: "user") {
    id
    name
  }
  post1: createPost(title: "Post 1", content: "Content 1", author_id: 1) {
    id
    title
  }
}
```

## 运行示例

### 查看所有可用的 Mutations
```bash
PYTHONPATH=. python3 demo/graphql/show_mutations.py
```

### 运行完整的 Mutation 示例
```bash
PYTHONPATH=. python3 demo/graphql/mutation_examples.py
```

## 特性说明

### 1. 两阶段执行
Mutation 使用两阶段执行，与 Query 相同：
- **Phase 1**: 执行 mutation 方法 → 构建响应模型 → 转换数据
- **Phase 2**: 使用 Resolver 解析关联数据（LoadBy、resolve_、post_）

### 2. 顺序执行
Mutations 顺序执行（不像 Query 那样并发），保证：
- 执行顺序可预测
- 事务一致性
- 前面的 mutation 可以影响后面的 mutation

### 3. 关联数据解析
Mutation 返回的实体支持关联数据解析：
```python
@mutation(name='createUser')
async def create_user(cls, name: str, email: str) -> 'UserEntity':
    return await db.create_user(name, email)
    # 返回的 UserEntity 可以包含 myposts, meta 等关联数据
```

### 4. 错误处理
- 业务逻辑错误：返回 `null` + errors 数组
- 验证错误：GraphQL 字段错误
- 意外错误：GraphQL 错误 + 异常详情

## 使用建议

### 参数命名
GraphQL 查询中的参数名需要使用 **snake_case** 以匹配 Python 函数参数：
- ✅ `create_user(name: "Alice")`
- ❌ `createUser(name: "Alice")`

### 返回类型
- 默认返回实体（非空）
- 使用 `Optional[T]` 表示可能返回 null
- 使用 `bool` 表示操作成功/失败

### 异步方法
所有 mutation 方法都是异步的，使用 `async def` 定义。

## 示例文件

- **entities.py** - 包含所有实体和 mutation 定义
- **mutation_examples.py** - 完整的 mutation 使用示例
- **show_mutations.py** - 显示所有可用的 mutations

## 下一步

1. 运行示例查看实际效果
2. 在 GraphiQL 中测试 mutations
3. 在你的项目中使用 `@mutation` 装饰器
4. 根据业务需求定制 mutation 逻辑
