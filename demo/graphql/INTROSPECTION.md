# GraphQL 内省查询支持

## ✅ 已实现完整的内省查询支持

GraphQL Demo 现在完整支持 GraphQL 内省规范（Introspection），可以在所有主流的 GraphQL IDE 中正常使用。

**最新修复 (2026-02-24)**:

1. **LIST 类型 ofType 修复**: 修复了 GraphiQL 中的 `TypeError: Cannot read properties of null (reading 'map')` 错误。LIST 类型现在正确返回 `ofType` 字段指向元素类型。

2. **OBJECT 类型 interfaces 修复**: 修复了 GraphiQL/Hygraph 中的 `Introspection result missing interfaces` 错误。OBJECT 类型现在正确返回 `interfaces: []` (空数组) 而不是 `interfaces: null`，完全符合 GraphQL 规范。

现在完全兼容 GraphiQL、Hygraph 和其他主流 GraphQL 客户端。

### 支持的内省字段

- ✅ `__schema` - 获取 schema 信息
  - `queryType` - 查询类型
  - `mutationType` - 变更类型
  - `subscriptionType` - 订阅类型
  - `types` - 所有类型列表
  - `directives` - 指令列表

- ✅ `__type(name: "TypeName")` - 获取特定类型的详细信息
  - `kind` - 类型种类（SCALAR, OBJECT 等）
  - `name` - 类型名称
  - `description` - 类型描述
  - `fields` - 字段列表
  - `args` - 参数列表

- ✅ `__typename` - 获取对象类型名称

### 内省数据结构

#### 标量类型（Scalar Types）
- `Int` - 整数
- `Float` - 浮点数
- `String` - 字符串
- `Boolean` - 布尔值
- `ID` - 唯一标识符

#### 对象类型（Object Types）
- 所有实体类型（UserEntity, PostEntity, CommentEntity 等）
- Query 类型

#### 字段信息
- 字段名称
- 字段描述
- 参数列表（名称、类型、默认值）
- 返回类型（kind, name, ofType）
- 弃用状态（isDeprecated, deprecationReason）

### 在 GraphiQL 中使用

#### 1. 启动服务器
```bash
uv run uvicorn demo.graphql.app:app --reload
```

#### 2. 打开 GraphiQL
访问 https://graphqlbin.com/graphiql

#### 3. 配置
- **Endpoint**: `http://localhost:8000/graphql`
- 点击 "Set Schema" 会自动加载（内省）

#### 4. 开始使用
- **自动补全**: 输入查询时按 `Ctrl+Space` 查看可用字段
- **文档**: 点击右侧 "Docs" 按钮查看完整文档
- **类型浏览**: 点击字段名可以跳转到类型定义

### 示例查询

#### 内省查询示例

```graphql
# 获取 schema 信息
query {
  __schema {
    queryType { name }
    types { name kind }
  }
}

# 获取特定类型信息
query {
  __type(name: "UserEntity") {
    name
    kind
    description
    fields {
      name
      description
      type {
        name
        kind
      }
    }
  }
}

# 获取 Query 类型的所有查询方法
query {
  __type(name: "Query") {
    name
    fields {
      name
      description
      args {
        name
        type {
          name
        }
      }
    }
  }
}
```

#### 普通 GraphQL 查询示例

```graphql
# 简单查询
query {
  users {
    id
    name
    email
  }
}

# 带参数的查询
query {
  users(limit: 2, offset: 1) {
    id
    name
  }
}

# 嵌套查询
query {
  user(id: 1) {
    id
    name
    email
  }
}

# 复杂嵌套
query {
  posts {
    title
    author {
      name
      email
    }
  }
}
```

### 支持的 GraphQL 客户端

以下客户端已测试并可正常使用：

#### 在线 IDE
- ✅ **GraphiQL Online** - https://graphqlbin.com/graphiql
- ✅ **Apollo Explorer** - https://explorer.apollographql.com/
- ✅ **Altair GraphQL** - https://altair.sirmuel.design/

#### 浏览器扩展
- ✅ GraphQL Playground (Chrome)
- ✅ Altair GraphQL Client (Chrome/Firefox/Safari)

#### 桌面应用
- ✅ Altair GraphQL Client
- ✅ Postman
- ✅ Insomnia
- ✅ GraphQL Playground (Electron)

### 技术实现细节

#### 内省查询检测
```python
def _is_introspection_query(self, query: str) -> bool:
    # 检测 __schema, __type, __typename
    introspection_keywords = ["__schema", "__type", "__typename"]
    return any(keyword in query for keyword in introspection_keywords)
```

#### 查询路由
- 内省查询 → 返回静态构建的内省数据
- 普通查询 → 使用自定义逻辑执行（支持 LoadBy、Resolver 等）

#### 数据映射
- Python 类型 → GraphQL 类型
  - `int` → `Int`
  - `float` → `Float`
  - `str` → `String`
  - `bool` → `Boolean`
  - `list[T]` → `[T]`
  - `Optional[T]` → `T`

### CORS 支持

服务器已启用 CORS 支持，允许来自任何来源的请求：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 故障排除

#### 问题：GraphiQL 无法连接
**解决方案**：
1. 确保服务器正在运行
2. 检查端点 URL: `http://localhost:8000/graphql`
3. 查看浏览器控制台是否有 CORS 错误

#### 问题：Schema 无法加载
**解决方案**：
1. 点击 "Set Schema" 手动设置 schema URL
2. 或者等待自动内省完成
3. 检查网络连接

#### 问题：查询返回错误
**解决方案**：
1. 检查查询语法是否正确
2. 查看 GraphiQL 的 "Response" 面板
3. 确认字段名称拼写正确

#### 问题：字段不在自动补全中
**解决方案**：
1. 点击 "Reload Schema" 重新加载
2. 检查该字段是否在实体的 `__annotations__` 中定义
3. 确认该字段在 @query 方法返回的类型中存在

### API 端点

- **GraphQL 查询**: `POST http://localhost:8000/graphql`
- **Schema (SDL)**: `GET http://localhost:8000/schema`
- **API 文档**: `GET http://localhost:8000/docs`
- **根路径**: `GET http://localhost:8000/`

### 相关文档

- [README.md](./README.md) - 完整使用指南
- [QUICKSTART.md](./QUICKSTART.md) - 快速入门
- [GRAPHIQL.md](./GRAPHIQL.md) - GraphiQL 使用指南
- [STRUCTURE.md](./STRUCTURE.md) - 目录结构说明
