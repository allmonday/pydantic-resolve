# pydantic-resolve MCP 能力构建计划

## 概述

在 pydantic-resolve 现有的 GraphQL 能力基础上，构建 MCP (Model Context Protocol) 支持，将 ErDiagram 通过 MCP 暴露给 AI Agent，支持渐进暴露（Progressive Disclosure）。

## 核心设计决策

- **App 粒度**: 每个 ErDiagram 对应一个 MCP app（支持多 app 场景）
- **渐进暴露**: 完整三层结构
  - Layer 0: 应用发现 (`list_apps`)
  - Layer 1: 操作列表 (`list_queries`, `list_mutations`)
  - Layer 2: 详细 Schema (`get_query_schema`, `get_mutation_schema`)
  - Layer 3: 执行 (`graphql_query`, `graphql_mutation`)
- **目录结构**: `pydantic_resolve/graphql/mcp/`

## 实现步骤

### Step 0: 修改 @query/@mutation 命名方式（前置任务）

**目标**: 参考 sqlmodel-graphql 的命名方式，修改 GraphQL 操作名称生成规则：
- 移除 `name` 参数
- 自动从 `entity_name + method_name` 生成 GraphQL 操作名称
- 使用 camelCase 风格：`entityPrefix + MethodCamel`（如 `userGetAll`, `postCreate`）

**命名规则**（参考 `sqlmodel_graphql/utils/naming.py`）:
```python
def to_camel_case(name: str) -> str:
    """Convert snake_case to camelCase."""
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])

def to_graphql_field_name(entity_name: str, method_name: str) -> str:
    """Generate GraphQL field name with entity prefix."""
    # Entity prefix: first letter lowercase, rest unchanged
    entity_prefix = entity_name[0].lower() + entity_name[1:]
    # Method name to camelCase
    method_camel = to_camel_case(method_name)
    # Combine: entityPrefix + MethodCamel (capitalize first letter of method)
    return f"{entity_prefix}{method_camel[0].upper()}{method_camel[1:]}"
```

**示例**:
- `UserEntity.get_all` -> `userEntityGetAll`
- `Post.create` -> `postCreate`
- `User.get_by_id` -> `userGetById`

#### 修改文件清单

**1. 新建 `pydantic_resolve/graphql/utils/naming.py`**
```python
"""Naming conversion utilities for GraphQL."""

from __future__ import annotations


def to_camel_case(name: str) -> str:
    """Convert snake_case to camelCase."""
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def to_graphql_field_name(entity_name: str, method_name: str) -> str:
    """Generate GraphQL field name with entity prefix.

    Examples:
        >>> to_graphql_field_name("User", "get_all")
        'userGetAll'
        >>> to_graphql_field_name("Post", "create")
        'postCreate'
    """
    entity_prefix = entity_name[0].lower() + entity_name[1:]
    method_camel = to_camel_case(method_name)
    return f"{entity_prefix}{method_camel[0].upper()}{method_camel[1:]}"
```

**2. 修改 `pydantic_resolve/graphql/decorator.py`**

移除 `name` 参数，只保留 `description`:

**3. 修改 `pydantic_resolve/graphql/schema/generators/sdl_generator.py`**

在 `_extract_query_methods` 和 `_extract_mutation_methods` 中使用 `to_graphql_field_name` 生成名称

**4. 修改 `pydantic_resolve/graphql/schema/generators/introspection_generator.py`**

同样更新命名逻辑

**5. 修改 `pydantic_resolve/graphql/handler.py`**

更新 `_build_query_map` 和 `_build_mutation_map`

**6. 更新 `demo/graphql/entities.py`**

移除 `name` 参数

### Step 1: 创建类型定义 (`types/`)

**文件**: `pydantic_resolve/graphql/mcp/types/app_config.py`
**文件**: `pydantic_resolve/graphql/mcp/types/errors.py`

### Step 2: 创建 TypeTracer (`builders/type_tracer.py`)

直接移植 sqlmodel-graphql 的 TypeTracer

### Step 3: 创建 Managers (`managers/`)

**文件**: `pydantic_resolve/graphql/mcp/managers/app_resources.py`
**文件**: `pydantic_resolve/graphql/mcp/managers/multi_app_manager.py`

### Step 4: 创建 MCP Tools (`tools/multi_app_tools.py`)

8 个工具:
1. `list_apps()`
2. `list_queries(app_name)`
3. `list_mutations(app_name)`
4. `get_query_schema(name, app_name, response_type)`
5. `get_mutation_schema(name, app_name, response_type)`
6. `graphql_query(query, app_name)`
7. `graphql_mutation(mutation, app_name)`

### Step 5: 创建 Server (`server.py`)

**文件**: `pydantic_resolve/graphql/mcp/server.py`

### Step 6: 扩展 SDLGenerator

添加 `generate_operation_sdl` 方法

## 文件清单

### 新建文件
1. `pydantic_resolve/graphql/utils/naming.py`
2. `pydantic_resolve/graphql/mcp/__init__.py`
3. `pydantic_resolve/graphql/mcp/server.py`
4. `pydantic_resolve/graphql/mcp/managers/__init__.py`
5. `pydantic_resolve/graphql/mcp/managers/app_resources.py`
6. `pydantic_resolve/graphql/mcp/managers/multi_app_manager.py`
7. `pydantic_resolve/graphql/mcp/builders/__init__.py`
8. `pydantic_resolve/graphql/mcp/builders/type_tracer.py`
9. `pydantic_resolve/graphql/mcp/tools/__init__.py`
10. `pydantic_resolve/graphql/mcp/tools/multi_app_tools.py`
11. `pydantic_resolve/graphql/mcp/types/__init__.py`
12. `pydantic_resolve/graphql/mcp/types/app_config.py`
13. `pydantic_resolve/graphql/mcp/types/errors.py`
14. `demo/graphql/mcp_server.py`

### 修改文件
1. `pydantic_resolve/graphql/decorator.py`
2. `pydantic_resolve/graphql/schema/generators/sdl_generator.py`
3. `pydantic_resolve/graphql/schema/generators/introspection_generator.py`
4. `pydantic_resolve/graphql/handler.py`
5. `demo/graphql/entities.py`

## 依赖

需要添加到 `pyproject.toml` 的 `dependencies`:
```toml
dependencies = [
    # ... existing dependencies ...
    "mcp>=1.0.0",
]
```

---

*设计文档已保存到 `pydantic_resolve/graphql/mcp/mcp_design.md`*

现在请确认是否可以开始实现。 🚀