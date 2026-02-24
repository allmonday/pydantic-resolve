# GraphQL Demo 更新日志

## 2026-02-24 - GraphQL 规范兼容性与多查询支持

### 修复的问题

#### 1. LIST 类型 introspection 修复 ✅
**问题**：GraphiQL 报错 `TypeError: Cannot read properties of null (reading 'map')`

**原因**：LIST 类型的内省返回 `ofType: null`，违反了 GraphQL 规范

**修复**：修改 `_get_introspection_query_fields()` 方法，确保 LIST 类型正确返回 `ofType` 指向元素类型

**文件**：`pydantic_resolve/graphql/handler.py` (lines 470-485)

**影响**：GraphiQL 和其他 GraphQL 客户端现在可以正确加载 schema

---

#### 2. OBJECT 类型 interfaces 修复 ✅
**问题**：Hygraph/GraphiQL 报错 `Introspection result missing interfaces`

**原因**：OBJECT 类型返回 `interfaces: null`，违反 GraphQL 规范（必须返回空数组 `[]`）

**修复**：所有 OBJECT 类型定义改为返回 `interfaces: []`

**文件**：`pydantic_resolve/graphql/handler.py`
- `_get_introspection_type()` (lines 274, 287)
- `_get_introspection_types()` (lines 362, 375)

**影响**：完全符合 GraphQL introspection 规范，所有主流 GraphQL 客户端都能正常工作

---

#### 3. 多根查询支持 ✅
**问题**：单次请求只返回第一个根查询的结果

**示例**：
```graphql
query {
  posts { id }      # ✅ 返回
  post(id: 1) { id } # ❌ 不返回
}
```

**原因**：
- `QueryParser._extract_root_field()` 只提取第一个根字段
- `QueryParser.parse()` 只构建一个字段的 field_tree
- `GraphQLHandler._execute_custom_query()` 只处理一个根字段

**修复**：
1. **QueryParser** (pydantic_resolve/graphql/query_parser.py):
   - 添加 `_extract_root_fields()` 方法返回所有根字段
   - 修改 `parse()` 方法为所有根字段构建 field_tree

2. **GraphQLHandler** (pydantic_resolve/graphql/handler.py):
   - 修改 `_execute_custom_query()` 遍历所有根查询
   - 收集所有查询结果到单个 data 对象
   - 添加错误处理（部分查询失败不影响其他查询）

**文件**：
- `pydantic_resolve/graphql/query_parser.py` (lines 31-82, 93-105)
- `pydantic_resolve/graphql/handler.py` (lines 528-603)

**影响**：
- ✅ 支持单次请求执行多个不同的根查询
- ✅ 向后兼容单个查询的请求
- ✅ 部分查询失败时，成功的查询仍会返回结果

---

### 测试验证

所有修复都通过了以下测试：

1. **Introspection 测试** ✅
   - `__schema` 查询
   - `__type(name: "TypeName")` 查询
   - SCALAR, OBJECT, LIST 类型正确性

2. **多查询测试** ✅
   - 两个根查询：`{ posts { } post(id:1) { } }`
   - 三个根查询：`{ posts { } users { } comments { } }`
   - 单查询向后兼容：`{ users { } }`

3. **错误处理测试** ✅
   - 部分查询失败不影响其他查询
   - 未知查询返回错误但不中断执行

---

### 兼容性

现在完全兼容以下 GraphQL 客户端：

- ✅ GraphiQL Online (https://graphqlbin.com/graphiql)
- ✅ Hygraph (https://hygraph.com)
- ✅ Apollo Explorer (https://explorer.apollographql.com/)
- ✅ Altair GraphQL Client (https://altair.sirmuel.design/)
- ✅ Postman
- ✅ Insomnia
- ✅ curl 和其他 HTTP 客户端

---

### 使用示例

#### 单个查询（向后兼容）
```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ users { id name } }"}'
```

#### 多个根查询（新功能）
```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ posts { id title } users { id email } }"}'
```

#### 带参数的多查询
```graphql
query {
  posts(limit: 2) {
    id
    title
  }
  post(id: 1) {
    title
    author {
      name
    }
  }
  users(role: "admin") {
    id
    name
  }
}
```

---

### API 变更

**破坏性变更**：无

**新增功能**：
- 多根查询支持
- 完整的 GraphQL introspection 规范兼容

**修复**：
- LIST 类型 ofType 字段
- OBJECT 类型 interfaces 字段

---

### 下一步

服务器启动命令（使用最新代码）：
```bash
uv run uvicorn demo.graphql.app:app --reload
```

测试端点：
- GraphQL: `POST http://localhost:8000/graphql`
- Schema (SDL): `GET http://localhost:8000/schema`
- API 文档: `GET http://localhost:8000/docs`
