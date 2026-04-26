# 四段论开发方法论 — 权限 Plugin 设计总结

> 基于 pydantic-resolve + AI 的分层开发模式，本文聚焦 Phase 3 权限 Plugin 的设计。

---

## 一、四段论框架回顾

| Phase | 职责 | 产出 |
|-------|------|------|
| **Phase 1** | Pydantic Schema + ER Diagram + 聚合根入口操作 | 业务实体定义，纯语义，不依赖数据源 |
| **Phase 2** | Loader 实现 + 测试 | 数据获取，数据源无关（ORM/HTTP RPC/Redis/ES） |
| **Phase 3** | 按 Use Case 组装 API 响应 + 权限 Plugin | API 响应结构 + 访问控制 |
| **Phase 4** | OpenAPI spec → TS SDK → 前端 UI | 端到端 SDK |

**核心原则：层间单向依赖，变更隔离。**

---

## 二、权限 Plugin 的设计哲学

### 2.1 类比中间表

```
多对多关系：
  User ── user_roles ──► Role
  User 不知道自己有哪些 Role
  Role 不知道自己被哪些 User 持有
  关系信息完全在中间表里

权限也是一样：
  User ── 权限规则 ──► Entity
  User 不知道自己对什么有权限
  Entity 不知道自己被什么权限规则保护
  关系信息完全在权限层（Plugin）
```

**Entity 保持纯粹的业务数据，不感知权限的存在。**

### 2.2 前提条件：ER Diagram + AutoLoad

Permission Plugin 依赖 ER Diagram + AutoLoad 模式，这是设计前提：

```
ER Diagram 知道关系结构 (user → dept → project → document)
    ↓
scope_desc 不需要手写，从视图的 AutoLoad 注解链自动推导
（或从 GraphQL 查询 AST 提取）
    ↓
权限系统返回的 scope 树和视图声明的结构天然对齐
    ↓
AutoLoad 已经知道如何沿关系加载数据，自然也知道如何用 scope 约束加载
```

不使用 ER Diagram 的项目（纯 Core API 模式）不在本 Plugin 的适用范围内。

### 2.3 为什么是 Plugin 而不是框架核心

| 场景 | 效果 |
|------|------|
| 不需要权限的项目 | 不加载 Plugin，零负担 |
| 需要权限的项目 | 在 Phase 3 加载 Plugin，AutoLoad 自动约束 |
| 更换权限策略 | 换 Plugin，Phase 1/2 不动 |
| 测试 | Entity 和 Loader 的测试完全不需要 mock 权限 |

### 2.4 Plugin 的归属

```
Phase 1: Entity + ER Diagram   纯业务，不知道权限存在           ✅
Phase 2: Loader                接受更少的 keys，不感知原因       ✅ 不感知权限规则
Phase 3: AutoLoad + Plugin     AutoLoad 读 scope 约束 Loader    ✅ 唯一知道 scope 的地方
                               Plugin 计算 scope 树 + 注册 hook 传播 scope
Phase 4: SDK / 前端            不知道后端怎么鉴权               ✅
```

---

## 三、核心机制：Scope 预计算 + 树状约束

### 3.1 总体流程

```
请求进入
  │
  │  user_id + action + 视图声明（AutoLoad 注解树）
  │
  ▼
① 从视图声明的 AutoLoad 注解自动推导查询结构（与 GraphQL 查询同构）
   视图声明决定了"查什么"（树形状），权限系统决定了"能查到什么"（约束）
   scope_tree = 视图声明 ∩ 权限允许
   │
   ▼
② scope 挂到根对象（类似 pagination_tree 的 attach）
   │
   ▼
③ AutoLoad 读取 scope 自动约束 Loader
   resolved_hooks 将子 scope 传播到 resolved children
   │
   ▼
④ Loader 收到约束（ID 集合或 filter 闭包），不感知权限
```

**视图组装与 GraphQL 的同构关系**：

scope 计算的输入——"需要查哪些层级的哪些实体"——本质上是一个树形查询结构。
这个结构和 GraphQL 查询是同构的：

| 场景 | 查询结构来源 | scope 计算输入 |
|------|-------------|---------------|
| GraphQL | GraphQL 查询字符串（`{ departments { projects { documents } } }`） | 从查询 AST 提取 |
| REST/视图 | 视图类中的 `Annotated[list[T], AutoLoad()]` 声明链 | 从 AutoLoad 注解链提取 |

两种场景的 scope 计算逻辑相同：**scope_tree = 视图结构 ∩ 权限规则**。
GraphQL 场景更简单（查询直接声明了树），REST 场景需要解析 AutoLoad 注解来获得树。

### 3.2 Step 1：权限系统查询

**输入**——层级描述（scope_desc）有两个来源，根据场景选择：

| 来源 | 适用场景 | 获取方式 |
|------|---------|---------|
| 视图 AutoLoad 注解 | REST/视图组装 | 从 `Annotated[list[T], AutoLoad()]` 声明链提取 |
| GraphQL 查询 AST | GraphQL 场景 | 从查询字符串直接解析 |

```python
# 方式一：从视图声明解析（REST 场景）
# UserScopeView → departments: AutoLoad → DepartmentScopeView → projects: AutoLoad → ...
# Plugin 扫描 AutoLoad 注解链，自动推导出：
scope_desc = {
    "departments": {
        "projects": {
            "documents": {}
        }
    }
}

# 方式二：从 GraphQL 查询提取（GraphQL 场景）
# query { departments { projects { documents { id name } } } }
# → 同样的 scope_desc

# 查询权限系统
scope_tree = await permission_plugin.compute_scope(
    user_id=123,
    action="read",
    scope_desc=scope_desc,  # 自动生成，非人工维护
)
```

**输出**——scope 树统一为两种形态：

| 形态 | 含义 | 典型场景 |
|------|------|---------|
| `ScopeFilter(ids=frozenset())` | 无权限，返回空 | 用户没有任何角色或权限 |
| dict 树 `{'departments': [...]}` | 有权限（含嵌套约束或无约束） | 用户有具体或全局权限 |

```json
// scoped access（具体权限）
{
  "departments": [
    {
      "id": 1,
      "projects": [{"id": 1}, {"id": 2}]
    },
    {
      "id": 3,
      "projects": [
        {"id": 5, "documents": [{"id": 7}]}
      ]
    }
  ]
}

// global access（全局权限，所有 dept ID 都列出，无子约束）
{
  "departments": [{"id": 1}, {"id": 2}]
}
```

关键特征：
- **层级描述自动生成**：从视图的 AutoLoad 注解链推导，与视图定义同源
- **树状输出**：保留层级关系，不是扁平 ID 列表
- **稀疏覆盖**：dept{1} 下 project{2} 没有 documents 子节点，意味着该分支无约束，AutoLoad 正常加载
- **只返回权限已知的部分**：不主动展开业务数据，避免"鸡生蛋"问题
- **全局权限也走 dict 树**：不使用 `ScopeFilter(ids=None)` 等特殊标记，而是在 `compute_scope_tree` 内查询所有 ID 并填充 dict 树。Loader 只处理具体 ID，不感知"全局"语义

**RBAC 和 ABAC 共用嵌套结构**，区别在于子节点的约束深度：

```json
// RBAC scope 树：子节点没有更深的约束节点
{
  "department": [
    {"id": 1, "project": [{"id": 1}, {"id": 2}]},
    {"id": 3, "project": [{"id": 5}]}
  ]
  // project{1} 的子节点 document 没有 document 子树 → 无约束，放行该 project 下所有 document
  // 即：父节点授权后，子孙节点默认全量放行
}

// ABAC scope 树：子节点可能有更深的约束（filter 闭包或嵌套 ID）
{
  "department": [
    {
      "id": 1,
      "project": [
        {"id": 1, "document": ScopeFilter(apply=...)},
        {"id": 2}
      ]
    }
  ]
  // project{1} 的 document 被 ScopeFilter 约束 → 只加载满足条件的 document
  // project{2} 的 document 无子约束 → 放行
}
```

RBAC 本质上每个类型只需要一层 ID 列表（用户能访问哪些 department、哪些 project），不需要按实例差异化约束子孙。但统一使用嵌套结构使得 Plugin 只需要一套传播逻辑，RBAC 只是"叶子节点为空对象"的特例。

### 3.3 Step 2：Scope 绑定到根对象

```python
# 类似 pagination 的 attach 方式
scope_tree = await permission_plugin.compute_scope(user_id, action, scope_desc)
object.__setattr__(root_instance, '_access_scope_tree', scope_tree)
```

### 3.4 根层设计：User 作为 Entity 的特殊性

**核心问题**：内层关系（Dept → Project → Document）基于 FK 字段，AutoLoad 的 `fk='id'` 直接映射到 Loader 的查询条件。但根层（User → Department）没有传统 FK——这个关系来自权限系统，不是来自数据模型。

**设计决策**：

```
内层：数据关系驱动
  DepartmentEntity.fk='id' → department_projects_loader(Project.department_id == fk)
  关系存在于 ER 中，AutoLoad 直接用 FK 字段

根层：权限关系驱动
  UserEntity.fk='id' → user_departments_by_scope_loader(scope_filter.ids)
  关系存在于权限系统中，FK 值 (user_id) 不直接用于查询
  scope_filter.ids 替代 FK 成为实际的查询条件
```

**User entity 的 `fk='id'` 是形式上的 FK**：
- AutoLoad 通过 `fk='id'` 读取 `self.id` (即 user_id)，构造 `LoadCommand(fk_value=user_id, scope_filter=...)`
- 但 loader 内部不使用 `fk_value` 做查询，而是用 `scope_filter.ids` 加载 department
- 这是合理的：User 和 Department 之间的关系确实来自权限系统，不是数据 FK

**关注点分离**：
- `compute_scope_tree`：负责将 user_id + action 转换为具体的 department ID 集合（含全局权限展开）
- `user_departments_by_scope_loader`：纯粹按 ID 加载数据，不感知权限语义
- `inject_access_scope` hook：负责将 scope 子树传播到 resolved children

根层 loader 的特殊性仅在于"FK 值不是查询条件"，这不违反关注点分离——loader 的契约是"接收 LoadCommand，返回数据"，至于用哪个字段查询，是 loader 的实现细节。

### 3.5 Step 3-4：AutoLoad 自动约束 + Hook 传播

**分工明确：AutoLoad 负责约束 Loader，resolved_hooks 负责传播 scope 到子节点。**

```
AutoLoad 读 scope → 只加载 dept {1, 3}
  │
  ├─ dept{1} resolved → hook 传播子 scope { project: [{id:1,...}, {id:2}] } 到 dept{1}
  │   │
  │   ├─ AutoLoad 读 scope → 只加载 project {1, 2}
  │   │   │
  │   │   ├─ project{1} → hook 传播子 scope { document: [{id:1}, {id:2}] }
  │   │   │   └─ AutoLoad 读 scope → 只加载 document {1, 2}
  │   │   │
  │   │   └─ project{2} → 无子 scope → AutoLoad 正常加载
  │   │
  │   └─ ...
  │
  └─ dept{3} resolved → hook 传播子 scope { project: ScopeFilter(...) } 到 dept{3}
      └─ AutoLoad 读 scope → 通过 filter 约束加载
          └─ project{5} → hook 传播子 scope { document: [{id:7}] }
              └─ AutoLoad 读 scope → 只加载 document {7}
```

**执行时序（基于 resolver.py 源码）：**

```
_execute_resolve_method_field:
  1. resolve 方法执行（AutoLoad 生成的） → 返回结果
  2. resolved_hooks 执行（inject_access_scope） → 向结果注入子 scope
  3. _traverse 递归进入结果 → 子节点的 AutoLoad 读取注入的 scope
```

hook 在 `_traverse` 之前执行，子节点被 traverse 时 scope 已经就绪。这个时序保证 AutoLoad 在下一层能读到 scope。

---

## 四、注入机制：AutoLoad 约束 + resolved_hooks 传播

### 4.1 和 Pagination 的同构关系

pydantic-resolve 的 GraphQL 分页已验证了 resolved_hooks + 隐藏字段注入的模式：

```
Pagination：
  _collect_pagination_tree()    → 从 GraphQL 查询构建分页树
  注入根对象                     → object.__setattr__(inst, _pag_tree, tree)
  resolved_hooks                → inject_nested_pagination(parent, field, result)
  子节点读取                     → 从树上取 PageArgs
  约束 DataLoader               → PageLoadCommand(fk, page_args) 作为 key

权限 Plugin（基于 ER Diagram）：
  ER Diagram Relationship 链    → 自动推导层级描述
  权限系统返回                   → 树状 scope（ID / filter / 无约束）
  注入根对象                     → object.__setattr__(root, _access_scope_tree, tree)
  AutoLoad                      → 读取 scope，约束 Loader（ID 或 filter）
  resolved_hooks                → inject_access_scope(parent, field, result)（scope 传播）
  子节点                        → AutoLoad 读取注入的 scope，继续约束
```

### 4.2 Hook 实现——按 ID 匹配传播子 scope

Hook 不做过滤，只负责将 scope 树从 parent 传播到 resolved children。scope 树是 per-ID 的，需要按 item ID 匹配对应的子树：

```python
def inject_access_scope(parent, field_name, result):
    """
    resolved_hook: 将 scope 树从 parent 传播到 resolved children。
    约束由 AutoLoad 在下一层 resolve 时自动完成。

    _access_scope_tree 可以是:
    - dict: {field_name: scope_value, ...} — per-field scope
    - ScopeFilter: 直接注入给所有 children（无子约束）
    """
    scope_tree = getattr(parent, '_access_scope_tree', None)
    if not scope_tree:
        return

    # ScopeFilter 作为根级 scope：注入给所有 children
    if isinstance(scope_tree, ScopeFilter):
        _inject_scope_to_result(scope_tree, result)
        return

    # Dict-based tree：按 field name 查找
    if field_name not in scope_tree:
        return

    child_scope = scope_tree[field_name]
    _inject_scope_to_result(child_scope, result)
```

**注入逻辑的分发**：

```python
def _inject_scope_to_result(child_scope, result):
    """注入 scope 到 result items 或单个对象。"""
    items = getattr(result, 'items', None) or (
        result if isinstance(result, list) else None
    )
    if items:
        if isinstance(child_scope, list):
            # ID 列表：按 item ID 匹配对应的子 scope
            scope_map = {
                s['id']: {k: v for k, v in s.items() if k != 'id'}
                for s in child_scope
            }
            for item in items:
                item_scope = scope_map.get(getattr(item, 'id', None))
                if item_scope is not None:
                    object.__setattr__(item, '_access_scope_tree', item_scope)
        else:
            # ScopeFilter 或其他：注入给所有 items
            for item in items:
                object.__setattr__(item, '_access_scope_tree', child_scope)
        return

    # 单个对象
    if hasattr(result, '__dict__'):
        object.__setattr__(result, '_access_scope_tree', child_scope)
```

**关键细节**：全局权限返回的 dict 树中，每个 dept 条目没有 `projects` 子键。Hook 按 field_name 查找时，`field_name='projects'` 不在空 dict 中 → 不注入 → AutoLoad 正常加载（无约束）。这保证了全局权限下所有子层级都正常展开。

### 4.3 AutoLoad 自动约束（实际实现）

AutoLoad 生成的 resolve 方法自动检查实例上的 `_access_scope_tree`，并通过 `LoadCommand` 传递 scope 约束给 Loader：

```python
# AutoLoad 生成的 resolve 方法（基于 er_diagram.py create_resolve_method）
def resolve_departments(self, loader=Loader(user_departments_by_scope_loader)):
    fk = getattr(self, 'id')  # fk='id' → UserEntity.id
    fld_name = 'departments'

    scope_tree = getattr(self, '_access_scope_tree', None)

    # 从 scope_tree 提取 field-specific scope
    if isinstance(scope_tree, ScopeFilter):
        field_scope = scope_tree  # ScopeFilter 直接作为 scope
    elif scope_tree:
        field_scope = scope_tree.get(fld_name)  # dict 树按 field name 查找
    else:
        field_scope = None

    # 构建 LoadCommand
    if field_scope is not None:
        scope_filter = _to_scope_filter(field_scope)  # 提取 ScopeFilter(ids=...)
        key_obj = LoadCommand(fk_value=fk, scope_filter=scope_filter)
        return loader.load(key_obj)
    else:
        return loader.load(fk)  # 无约束，正常加载
```

**`_to_scope_filter` 的转换逻辑**：
- `[{id:1}, {id:2}]` → `ScopeFilter(ids=frozenset({1, 2}))`
- `ScopeFilter(ids=...)` → 原样返回
- dict 树被转换为 `ScopeFilter(ids=...)`，只取第一层 ID

使用者不需要写任何 scope 相关代码，`AutoLoad()` 声明即可：

```python
class UserScopeView(UserEntity):
    """User → departments via scope-aware AutoLoad."""
    departments: Annotated[list[DepartmentScopeView], AutoLoad()] = []

class DepartmentScopeView(DepartmentEntity):
    projects: Annotated[list[ProjectScopeView], AutoLoad()] = []

class ProjectScopeView(ProjectEntity):
    documents: Annotated[list[DocumentScopeView], AutoLoad()] = []
```

### 4.4 GraphQL 和 REST 统一

```
GraphQL 路径和 REST/Resolver 路径最终都汇聚到：
  Resolver._execute_resolve_method_field()
    → resolved_hooks 循环

一个注入点，两种路径统一。
```

### 4.5 端到端调用示例

```python
# --- Phase 1: Entity + ER Diagram ---
class UserEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(
            fk='id',
            name='departments',
            target=list[DepartmentEntity],
            loader=user_departments_by_scope_loader,  # 根层 scope-aware loader
        )
    ]
    id: int
    name: str

class DepartmentEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='id', name='projects', target=list[ProjectEntity], loader=projects_loader)
    ]
    id: int
    name: str

class ProjectEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='id', name='documents', target=list[DocumentEntity], loader=documents_loader)
    ]
    id: int
    name: str
    dept_id: int

class DocumentEntity(BaseModel, BaseEntity):
    id: int
    title: str
    project_id: int

diagram = BaseEntity.get_diagram()
AutoLoad = diagram.create_auto_load()
config_global_resolver(diagram)

# --- Phase 2: Loaders ---

async def user_departments_by_scope_loader(keys):
    """根层 scope-aware loader：按 scope_filter.ids 加载 departments。
    纯数据加载，不感知权限语义。"""
    scope_filters = [k.scope_filter for k in keys if isinstance(k, LoadCommand)]

    all_ids = set()
    for sf in scope_filters:
        if sf and sf.ids:
            all_ids.update(sf.ids)

    if not all_ids:
        return [[] for _ in keys]

    rows = await session.scalars(select(Department).where(Department.id.in_(all_ids)))
    obj_map = {d.id: d for d in rows}

    results = []
    for sf in scope_filters:
        if sf and sf.ids:
            results.append([obj_map[did] for did in sorted(sf.ids) if did in obj_map])
        else:
            results.append([])
    return results

# 内层 loader 不需要知道 scope，AutoLoad 通过 LoadCommand 传递约束
async def projects_loader(keys):
    """内层 loader：支持 LoadCommand 中的 scope_filter 约束。"""
    ...

# --- Phase 3: API 响应 + 权限 Plugin ---

class UserScopeView(UserEntity):
    departments: Annotated[list[DepartmentScopeView], AutoLoad()] = []

class DepartmentScopeView(DepartmentEntity):
    projects: Annotated[list[ProjectScopeView], AutoLoad()] = []

class ProjectScopeView(ProjectEntity):
    documents: Annotated[list[DocumentScopeView], AutoLoad()] = []

class DocumentScopeView(DocumentEntity):
    pass

# FastAPI endpoint
@app.get("/users/{user_id}/scope-tree")
async def get_user_scope_tree(user_id: int = Depends(get_current_user_id)):
    # 1. 计算 scope 树（三种返回值之一）
    scope_tree = await compute_scope_tree(user_id, "read")
    # - ScopeFilter(ids=frozenset()): 无权限
    # - {'departments': [{'id': 1}, {'id': 2}]}: 全局权限
    # - {'departments': [{'id': 1, 'projects': [{'id': 1}]}]}: scoped 权限

    # 2. 构建根对象并挂载 scope
    root = UserScopeView(id=user_id, name=user_name)
    object.__setattr__(root, '_access_scope_tree', scope_tree)

    # 3. resolve（AutoLoad 自动约束 + hook 传播 scope）
    result = await Resolver(
        resolved_hooks=[inject_access_scope],
        enable_from_attribute_in_type_adapter=True,
    ).resolve(root)
    return result
```

---

## 五、各组件职责分工

```
┌──────────────────────────────────────────────────────────┐
│  Phase 3: 权限 Plugin + AutoLoad                          │
│                                                          │
│  Plugin:                                                  │
│  ① 从 ER Diagram 自动推导层级描述                         │
│  ② 调用权限系统，获取树状 scope                            │
│  ③ 将 scope 挂到根对象                                    │
│  ④ 注册 resolved_hook 用于 scope 传播                     │
│                                                          │
│  AutoLoad:                                                │
│  ⑤ 读取实例上的 _access_scope_tree                        │
│  ⑥ 根据 scope 形态（ID / filter / 无约束）约束 Loader     │
│                                                          │
│  resolved_hooks:                                          │
│  ⑦ 将子 scope 传播到 resolved children                    │
│                                                          │
│  Entity 不知道 │ Loader 不知道 │ 使用者不知道 │ 前端不知道 │
└──────────────────────────────────────────────────────────┘
```

Loader 接受 scope 约束，和接受 PageArgs 分页参数是同一件事——**都是获取数据时的范围限制，不感知来源。**

---

## 六、Scope 的三种形态与 ABAC 覆盖

### 6.1 后置过滤破坏分页

```
请求：GET /documents?page=1&limit=10

后置过滤（post_* 或 resolved_hooks 过滤）：
  DB 返回 10 条 → 过滤后剩 3 条 → 用户要 10 条只拿到 3 条
  total_count 不反映有权数据的真实数量
  has_more 无法判断（不知道后续页面还有没有有权的记录）
  → 分页的两个基石（总数、偏移）全部失效
```

后置过滤意味着权限判断在数据查询之后，分页器在查询时不知道哪些记录会被过滤掉。**Scope 预计算把权限从"查询后判断"变成"查询前已知"，是分页与权限共存的必要条件。**

### 6.2 Scope 的两种输出形态

ABAC 条件依赖资源属性，无法总是预计算为 ID 集合。`compute_scope_tree` 的输出统一为两种形态：

| scope 形态 | 含义 | `compute_scope_tree` 返回值 | Loader 行为 |
|-----------|------|---------------------------|-------------|
| 无权限 | 用户没有任何角色或权限 | `ScopeFilter(ids=frozenset())` | 返回空列表 |
| 有权限 | 有具体或全局权限 | dict 树 `{'departments': [{'id': 1, ...}]}` | 按 ID 加载 |

dict 树内部通过子节点的有无区分约束粒度：

| 子节点形态 | 含义 | AutoLoad / DataLoader 行为 |
|-----------|------|---------------------------|
| `[{id:1}, {id:2}]` | 精确允许的资源 | `WHERE id IN (1, 2)` |
| Filter 闭包 `ScopeFilter(apply=...)` | 规则覆盖大量资源 | 闭包 append 到 query |
| 无子节点 | 全量放行 | 正常加载，不约束 |

**关键设计决策：全局权限不使用特殊标记**

全局权限在 `compute_scope_tree` 内部查询所有 department ID，填充为 `{'departments': [{'id': 1}, {'id': 2}, ...]}`。
每个 dept 条目没有 `projects` 子键，所以 hook 传播时不会注入子约束，AutoLoad 在内层正常加载。
这样 Loader 永远只处理具体 ID，不感知"全局"语义。

**Filter 以闭包形式传递，在权限系统内部捕获用户上下文：**

```python
# 权限系统内部，捕获 user context 创建闭包
def compute_scope(user, action, scope_desc):
    return {
        "document": ScopeFilter(
            apply=lambda q: q.filter(
                Document.classification_level <= user.clearance_level
            )
        )
    }

# DataLoader 端，只调用闭包，不知道 user context
def batch_load_fn(self, keys):
    query = session.query(Document).filter(Document.id.in_(keys))
    if scope_filter:
        query = scope_filter.apply(query)  # 闭包调用，user context 已封装在内
    return query.all()
```

- **DataLoader 不知道 user context**——闭包已捕获
- **类型安全**——用 ORM 方法而非裸 SQL，避免注入
- **可测试**——闭包可以独立测试
- **数据库无关**——闭包内部用 ORM 抽象，不绑定具体 SQL 方言

filter 来源不一定是权限——搜索条件、业务规则也可以复用同一机制。对 DataLoader 来说只是"支持条件过滤"这个通用能力。

**ScopeFilter 的限制：**
- **不跨进程**：闭包无法序列化，scope 树仅在单进程内使用。如果需要跨进程传递（如微服务架构），应使用 ID 列表形态而非 filter 闭包
- **DataLoader batching 兼容**：当 DataLoader 批量收到多个 key 时，同一批次内共享同一个 ScopeFilter（同一层级、同一权限规则），闭包对所有 key 统一 apply，不影响 batching 效率

### 6.3 ABAC 场景覆盖分析

权限系统内部将 RBAC/ABAC 规则翻译为对应的 scope 形态：

```
┌──────────────────────────────────────────────────┐
│  阶段一：权限系统（内部可以很复杂）                 │
│                                                  │
│  RBAC:  role → permission → 输出嵌套 ID 树（叶子无子约束）  │
│  ABAC:  用户属性 + 资源规则 → 输出嵌套 scope 树（含 filter）  │
│  管理员: 输出无约束                                           │
│                                                             │
│  不论内部怎么算，输出格式统一：嵌套 scope 树                    │
│  RBAC 和 ABAC 共用一套传播逻辑，RBAC 是"叶子为空"的特例        │
└──────────────────────┬───────────────────────────┘
                       │
          契约：输入 user_id + action + 层级描述
                输出 嵌套 scope 树（ID 列表 / filter 闭包 / 无约束）
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│  阶段二：数据加载                                  │
│                                                  │
│  AutoLoad 读 scope → 根据 ID 或 filter 约束加载    │
│  DataLoader 支持 filter append → 通用能力，非权限   │
└──────────────────────────────────────────────────┘
```

| ABAC 场景 | 权限系统输出 | filter 能覆盖 |
|-----------|-------------|--------------|
| 部门归属 | ID 列表 或 filter 闭包 | 能 |
| 资源密级 | `ScopeFilter(apply=lambda q: q.filter(level <= user.clearance))` | 能 |
| 所有者 | `ScopeFilter(apply=lambda q: q.filter(created_by == user.id))` | 能 |
| 审批状态流转 | 复杂 OR 条件闭包 | 能，但复杂 |
| 时间窗口 | `ScopeFilter(apply=lambda q: q.filter(effective_date <= func.now()))` | 能 |
| 地域合规 | 非 EU 用户：filter 闭包；EU 用户：无约束 | 能 |
| 跨数据源判断 | 需要外部 RPC → 无法编译为 filter | 不能，降级为后置过滤 |
| 非 SQL 的 Python 逻辑 | 无法编译为 SQL/ORM 操作 | 不能，降级为后置过滤 |
| 动态配额 | 运行时状态，scope 无法预知 | 不能，降级为后置过滤 |

**filter 方案覆盖约 85% 的 ABAC 场景**，剩余场景降级为后置过滤（接受不分页的限制），或由权限系统内部预查询外部系统后将结果转为 ID 列表。

---

## 七、可参考的系统

| 系统 | 参考点 | 局限 |
|------|--------|------|
| **Google Zanzibar / SpiceDB** | 关系遍历、LookupResources 反向展开 scope | 输出扁平 ID，不保留层级 |
| **Hasura** | 权限规则编译成 SQL WHERE | 无层级继承展开 |
| **OPA Partial Evaluation** | 策略编译成查询约束 | 不知业务树结构 |
| **AWS IAM** | Deny 优先 + 通配符继承 | 扁平评估，不做树合并 |

**创新点**：Zanzibar 的关系遍历 + Hasura 的约束编译 + OPA 的策略求值，三者结合，通过 pydantic-resolve 的 resolved_hooks 约束 DataLoader。

---

## 八、待解决的问题

1. ~~**权限树未覆盖分支的处理**~~：已决——scope 只包含有显式授权的分支，未覆盖的部分默认拒绝（hook 不注入 → AutoLoad 无约束加载 → 但根层 scope 已限制了可见的 dept/project ID，未覆盖的 dept 本身不会被加载）
2. ~~**Loader key 替换的时机**~~：已决——AutoLoad 自动读取 scope 约束 Loader，不需要手动处理
3. **scope 缓存**：同一用户短时间内的 scope 可复用
4. **Allow/Deny 跨层级传播**：树上某节点的 deny 如何截断子节点的 allow
5. **scope_desc 自动生成**：目前 `compute_scope_tree` 硬编码了层级结构（department → project → document），应从视图的 AutoLoad 注解链自动提取
6. **根层 FK 语义**：User entity 的 `fk='id'` 是形式上的 FK，实际查询使用 scope_filter.ids。需要评估是否需要在 Relationship 中增加 `scope_driven=True` 标记来区分
7. **GraphQL scope 集成**：GraphQL 查询 AST 已天然包含查询结构，scope 计算可直接复用。需要验证 GraphQLHandler + scope 的集成路径

---

## 九、现有参考实现

- `demo/rbac/` — RBAC/ABAC demo（含 scope 预计算模式）
  - `entities.py`：资源实体（User/Department/Project/Document）+ 权限实体（Permission/RolePermission/Role/UserRole/GroupRole/MailGroup）的 ER Diagram 定义
  - `loaders.py`：scope-aware loaders（含 `user_departments_by_scope_loader`）+ 映射 loaders（`project_dept_mapping_loader`, `doc_project_mapping_loader`）
  - `scope.py`：`compute_scope_tree`（loader 驱动的权限查询 + ScopeNode 树构建）+ `inject_access_scope`（resolved_hook）
  - `condition.py`：命名条件注册表（`ConditionDef` + `build_scope` 返回 `(ids, apply)` 元组）
  - `schemas.py`：Scenario F — UserScopeView 使用 AutoLoad + scope 的完整示例
  - `demo.py`：Scenario 6 — Eve（scoped）、Alice（global）、Bob（global）三个用户的完整 demo
- `pydantic_resolve/graphql/pagination/` — 分页注入机制（scope 的同构参考）
  - `injector.py`：inject_nested_pagination 的实现
  - `types.py`：PageArgs / PageLoadCommand 的定义
- `pydantic_resolve/types.py` — `ScopeFilter`, `ScopeNode`, `LoadCommand` 核心类型
- `pydantic_resolve/utils/er_diagram.py` — `create_resolve_method`（AutoLoad scope 处理逻辑）+ `resolve_scope_filter` helper

---

## 十、实现状态与设计偏差

> 以下记录文档设计（一~九节）与实际实现之间的差异，用于指导后续更新。

### 10.1 Scope 树数据结构：dict → ScopeNode

文档基于 dict-keyed scope 树，实际已迁移到 `ScopeNode` dataclass：

| 维度 | 文档设计 | 实际实现 |
|------|---------|---------|
| 数据结构 | dict-keyed: `{'departments': [{'id': 1, 'projects': [...]}]}` | `list[ScopeNode]`: `[ScopeNode(type='departments', ids=[1], children=[...])]` |
| 查找方式 | `scope_tree.get(field_name)` / `field_name not in scope_tree` | `resolve_scope_filter(scope_tree, field_name)` + `e.type == field_name` |
| ID 存储 | `{'id': 1}` 单个 dict 条目 | `ScopeNode(ids=[1])` 批量 ids 列表 |
| 子树嵌套 | `{'id': 1, 'projects': [{'id': 2}]}` | `ScopeNode(ids=[1], children=[ScopeNode(type='projects', ids=[2])])` |

**待更新章节**：4.2（hook 代码示例）、4.3（AutoLoad scope 处理）、4.5（端到端示例）

### 10.2 Scope 输出形态：两种 → 三种

文档 3.2 节说输出统一为两种形态。实际有三种：

| 文档 | 实际 |
|------|------|
| `ScopeFilter(ids=frozenset())` = 无权限 | `'empty'` sentinel |
| dict 树 = 有权限 | `list[ScopeNode]` |
| （未提及） | `'all'` sentinel = 全局无约束权限 |

### 10.3 全局权限处理策略

文档设计决策："全局权限不使用特殊标记"——`compute_scope_tree` 内部查询所有 dept ID，填充为完整 dict 树。

实际实现：无条件全局权限直接返回 `'all'` sentinel；有条件的全局权限走 `_build_global_scope` 返回 ScopeNode 列表。

`'all'` sentinel 打破了文档中"Loader 永远只处理具体 ID"的设计——`user_departments_by_scope_loader` 已处理 `ids=None`（无约束加载所有）。

### 10.4 `_to_scope_filter` 已移除

文档 4.3 节描述的 `_to_scope_filter` 已完全移除，替换为：
- `ScopeNode.to_scope_filter()` 实例方法（`ids` → `ScopeFilter(ids=frozenset)`）
- `resolve_scope_filter(scope_tree, fld_name)` helper（从 ScopeNode 列表按 type 查找并转换）

### 10.5 inject_access_scope hook 更新

| 维度 | 文档 | 实际 |
|------|------|------|
| 匹配方式 | `field_name not in scope_tree`（dict key） | `[e for e in scope_tree if e.type == field_name]`（ScopeNode 属性） |
| ScopeFilter 分发 | `isinstance(scope_tree, ScopeFilter)` | `scope_tree in ('all', 'empty')` 哨兵判断 |
| ID→子树映射 | `scope_map = {s['id']: {k:v ...} for s in child_scope}` | `entry.ids` → `id_to_children` dict |

### 10.6 命名条件系统（condition.py）

文档未提及，实际已实现：
- `ConditionDef` dataclass：`evaluate(subject_attrs, resource_attrs) → bool` + `build_scope(subject_attrs) → (ids, apply)`
- `REGISTRY` 注册表 + `register()` / `get_condition()`
- 三个预定义条件：`same_dept`, `same_dept_non_confidential`, `public_internal_only`
- `build_scope` 返回 `(ids, apply)` 元组——ids 用于 RBAC ID 约束，apply 用于 ABAC filter 闭包

这是 ABAC 场景的核心扩展点，文档 6.2 节描述了 filter 闭包概念但未说明条件注册机制。

### 10.7 权限实体的 ER Diagram 声明

`entities.py` 新增了 6 个权限实体，与 4 个资源实体共享同一个 `BaseEntity = base_entity()`：

```
PermissionEntity (leaf)
RolePermissionEntity → permission → PermissionEntity
RoleEntity → role_permissions → list[RolePermissionEntity]
UserRoleEntity → role → RoleEntity
GroupRoleEntity → role → RoleEntity
MailGroupEntity (leaf)
```

### 10.8 `compute_scope_tree` 从 raw SQL 重构为 loader 调用

`compute_scope_tree` 不再直接操作数据库（无 `session_factory` / `select` / ORM model 引用），改为调用已声明的 loader：

| 步骤 | 旧实现（raw SQL） | 新实现（loader 调用） |
|------|---|---|
| 收集 direct role_ids | `session.scalars(select(UserRole...)` | `user_roles_loader([user_id])` |
| 收集 group role_ids | `session.scalars(select(GroupRole...)` | `group_role_ids_loader(group_ids)` |
| 查询权限详情 | `session.execute(select(RolePermission, Permission).join...)` | `role_permissions_loader(role_ids)` |
| global scope dept_ids | `session.scalars(select(UserDepartment...)` | `user_departments_loader([user_id])` |
| project→dept 映射 | `session.scalars(select(Project)...)` | `project_dept_mapping_loader(proj_ids)` |
| doc→project 映射 | `session.scalars(select(Document)...)` | `doc_project_mapping_loader(doc_ids)` |

### 10.9 compute_scope_tree 未利用 ER Diagram 驱动层级结构

虽然已从 raw SQL 重构为 loader 调用，但层级结构仍手动硬编码：

- 类型名 `'departments'`、`'projects'`、`'documents'` 写死在 `_build_scope_nodes` / `_build_project_nodes` 中
- ER Diagram 已声明 `DepartmentEntity → projects` / `ProjectEntity → documents`，但 `compute_scope_tree` 没有利用这些声明
- 新增层级（如 Project → Folder → Document）需手写新的 `_build_*_nodes` 函数

这是 `scope_desc` 功能（第八节 #5）要解决的问题。

### 10.10 `apply` 闭包在 ScopeNode 中的传播

文档描述了 `apply` 闭包通过 ScopeFilter 传递给 Loader，但未说明 `ScopeNode.apply` 在 hook 传播时的行为：

- `inject_access_scope` 只传播 `children`，不传播当前层级的 `apply`
- `apply` 只在 `to_scope_filter()` 时被消费（从 ScopeNode 转为 ScopeFilter）
- `apply` 是 per-level 的，不会向下继承

### 10.11 `resource_type_ref` vs `resource_type`

`role_permissions_loader` 返回的 dict 使用 `resource_type_ref`（来自 `RolePermission.resource_type`，多态的关联资源类型），而非 `resource_type`（来自 `Permission.resource_type`，权限定义中的目标资源类型）。文档 3.2 节的代码使用 `resource_type_ref` 但未解释两者区别。

### 10.12 待更新章节索引

| 章节 | 需要更新的内容 |
|------|---------------|
| 3.2 Step 1 输出 | 更新为三种形态（'all' / 'empty' / list[ScopeNode]），更新代码示例 |
| 3.2 关键特征 | "全局权限也走 dict 树" → 全局权限返回 `'all'` sentinel |
| 4.2 Hook 实现 | 全面更新为 ScopeNode 版本，删除 dict-based 代码示例 |
| 4.3 AutoLoad 自动约束 | 删除 `_to_scope_filter` 描述，改为 `resolve_scope_filter` + `ScopeNode.to_scope_filter()` |
| 4.5 端到端示例 | 更新 `compute_scope_tree` 为无 SQL 版本，更新 scope 绑定代码 |
| 6.2 scope 形态表 | 增加 'all'/'empty' sentinel 说明 |
| 八 待解决问题 #5 | scope_desc 自动生成 — 下一步开发目标 |
| 九 参考实现 | 增加 condition.py、权限实体 ERD 声明、types.py |
