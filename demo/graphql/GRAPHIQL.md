# 在 GraphiQL 中使用 GraphQL Demo

## ✅ 已修复的问题

### 1. CORS 支持
已在 `app.py` 中添加 CORS 中间件，支持跨域请求：
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Schema 端点改进
`/schema` 端点现在返回纯文本 SDL 格式（而非 JSON），更适合 GraphiQL 等工具解析。

### 3. 内省查询支持 (最新修复)
**修复日期**: 2026-02-24

完整实现 GraphQL 内省规范，支持：
- `__schema` 查询 - 获取 schema 信息
- `__type(name: "TypeName")` 查询 - 获取特定类型详情
- `__typename` 查询 - 获取对象类型名称

**修复 1: LIST 类型 ofType**

修复了 LIST 类型的 `ofType` 字段返回 `null` 的问题。现在 LIST 类型正确返回 `ofType` 指向元素类型。

```python
# 修复前 (导致 GraphiQL TypeError)
{
  "kind": "LIST",
  "name": null,
  "ofType": null  # ❌
}

# 修复后
{
  "kind": "LIST",
  "name": null,
  "ofType": {     # ✅
    "kind": "OBJECT",
    "name": "UserEntity",
    "ofType": null
  }
}
```

**修复 2: OBJECT 类型 interfaces**

修复了 OBJECT 类型的 `interfaces` 字段返回 `null` 的问题。根据 GraphQL 规范，OBJECT 类型必须返回 `interfaces: []` (空数组) 而不是 `null`。

```python
# 修复前 (导致 GraphiQL/Hygraph 错误)
{
  "kind": "OBJECT",
  "name": "UserEntity",
  "interfaces": null  # ❌ 违反 GraphQL 规范
}

# 修复后
{
  "kind": "OBJECT",
  "name": "UserEntity",
  "interfaces": []   # ✅ 符合 GraphQL 规范
}
```

这两个修复确保了与 GraphiQL、Hygraph、Apollo Explorer 等所有主流 GraphQL 客户端的完全兼容。

## 使用方法

### 启动服务器
```bash
uv run uvicorn demo.graphql.app:app --reload
```

### 在 GraphiQL Online 中使用

访问: https://graphqlbin.com/graphiql

配置：
- **GraphQL Endpoint**: `http://localhost:8000/graphql`
- **Schema URL**: `http://localhost:8000/schema`

### 示例查询

```graphql
# 获取所有用户
query {
  users {
    id
    name
    email
    role
  }
}

# 获取用户及其文章（嵌套查询）
query {
  user(id: 1) {
    id
    name
    email
    posts {
      id
      title
      content
      status
    }
  }
}

# 获取文章及作者
query {
  posts {
    id
    title
    content
    author {
      id
      name
      email
    }
  }
}

# 三层嵌套 - 评论、作者和文章
query {
  comments {
    id
    text
    author {
      name
      email
    }
    post {
      title
      author {
        name
      }
    }
  }
}

# 带参数的查询
query {
  users(limit: 2, offset: 1) {
    id
    name
  }
}

# 按状态筛选
query {
  posts(status: "published") {
    id
    title
  }
}
```

## 其他推荐的 GraphQL 客户端

### 在线工具
1. **Apollo Explorer**: https://explorer.apollographql.com/
2. **Altair Online**: https://altair.sirmuel.design/

### 浏览器扩展
1. **Chrome**: GraphQL Playground
2. **Firefox**: GraphQL Network Inspector
3. **Safari/Chrome**: Altair GraphQL Client

### 桌面应用
1. **Altair GraphQL Client** (跨平台)
2. **Postman** (支持 GraphQL)
3. **Insomnia** (支持 GraphQL)

## 常见问题

### OPTIONS 请求 405 错误
已通过添加 CORS 中间件修复。

### Schema 无法加载
确保：
1. 服务器正在运行
2. URL 正确: `http://localhost:8000/schema`
3. 防火墙没有阻止本地请求

### 查询返回空数据
检查实体定义中的 `@query` 方法是否正确返回数据。
