# GraphQL Demo 使用指南

## ⚠️ 重要提示

**必须使用项目的虚拟环境，不要使用系统 Python！**

## 1. 安装依赖

```bash
# 在项目根目录执行
uv pip install fastapi uvicorn graphql-core
```

## 2. 启动服务器

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

## 3. 测试查询

### 获取所有用户
```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ users { id name email role } }"}'
```

### 获取单个用户
```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ user(id: 1) { id name email } }"}'
```

### 获取所有文章
```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ posts { id title content } }"}'
```

### 嵌套查询 - 文章及作者
```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ posts { title author { name email } } }"}'
```

## 4. 查看文档

- **API 文档**: http://localhost:8000/docs
- **Schema**: http://localhost:8000/schema
- **根路径**: http://localhost:8000/

## 5. 快速测试脚本

```bash
# Python 测试（无需服务器）
uv run python demo/graphql/test_demo.py

# Curl 测试（需要服务器先启动）
cd demo/graphql
./test_queries.sh
```

## 常见错误

### ❌ ImportError: cannot import name 'create_graphql_route'

**原因**: 该函数已被移除，请使用 `GraphQLHandler` 直接集成。

**解决**:
```bash
# 确保在项目根目录
cd /Users/tangkikodo/Documents/pydantic-resolve

# 安装依赖
uv pip install fastapi uvicorn graphql-core

# 使用 uv run 启动
uv run uvicorn demo.graphql.app:app --reload
```

**注意**: 新版本使用 `GraphQLHandler`，详见 `app.py` 和 [集成指南](../../docs/graphql-integration.zh.md)。

### ❌ ModuleNotFoundError: No module named 'pydantic'

**原因**: 未安装项目依赖。

**解决**:
```bash
uv pip install pydantic fastapi graphql-core uvicorn
```

## 更多信息

- 详细文档: [README.md](./README.md)
- 快速入门: [QUICKSTART.md](./QUICKSTART.md)
- 目录结构: [STRUCTURE.md](./STRUCTURE.md)
