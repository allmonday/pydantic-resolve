# Demo 目录

此目录包含 pydantic-resolve 的演示应用。

## GraphQL Demo

`demo/graphql/` 目录提供了一个完整的 FastAPI + GraphQL 应用，展示了 pydantic-resolve 的 GraphQL 查询功能。

### 快速开始

1. **启动服务器**

```bash
# 方式1: 使用启动脚本（推荐）
cd demo/graphql
./run.sh

# 方式2: 直接运行
uv run python -m demo.graphql.app
```

2. **测试查询**

```bash
# 获取所有用户
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ users { id name email role } }"}'

# 获取单个用户
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ user(id: 1) { id name email } }"}'

# 获取所有文章
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ posts { id title content } }"}'
```

3. **查看文档**

访问 `http://localhost:8000/docs` 查看 FastAPI 自动生成的 API 文档。

### 更多信息

详细文档请查看 [demo/graphql/README.md](./graphql/README.md)
