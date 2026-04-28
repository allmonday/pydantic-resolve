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
scope_key 不需要手写，从 Relationship.name 自动对应
    ↓
权限系统返回的 flat dict 和视图声明的结构天然对齐
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
                               Plugin 计算 scope dict + 注册 hook 传播 scope
Phase 4: SDK / 前端            不知道后端怎么鉴权               ✅
```

---

## 三、核心机制：Scope 预计算 + Flat Dict 约束

### 3.1 总体流程

```
请求进入
  │
  │  user_id + action
  │
  ▼
① 权限系统查询，输出 flat dict: dict[str, ScopeFilter]
   key 是 AutoLoad 字段名（与 Relationship.name 对齐）
   value 是该层级的约束（ids / is_all / filter_fn）
   │
   ▼
② scope dict 挂到根对象: object.__setattr__(root, '_user_scope', scope_dict)
   │
   ▼
③ AutoLoad 读取 scope: scope_dict.get(field_name) → ScopeFilter
   resolved_hooks 将同一个 dict 引用传播到 resolved children
   │
   ▼
④ Loader 收到 LoadCommand(fk_value=fk, scope_filter=...)，按约束查询
```

**关键认知：权限不需要组装成树。**

Resolver 的递归遍历自然产生层级结构（Dept → Project → Document）。
权限只需要告诉每一层"你能访问哪些"，不需要把层级关系再编码一遍。
同一份 flat dict 在所有层级共享，每层通过自己的字段名取出对应的约束。

```
_user_scope = {
    "departments": ScopeFilter(is_all=True),
    "projects": ScopeFilter(ids=frozenset({1, 3})),
    "documents": ScopeFilter(ids=frozenset({10})),
}

DeptView.resolve_projects:
    scope_filter = _user_scope.get("projects")  → ScopeFilter(ids={1,3})
    → LoadCommand(fk_value=dept_id, scope_filter=ScopeFilter(ids={1,3}))

    ProjectView.resolve_documents:
        scope_filter = _user_scope.get("documents")  → ScopeFilter(ids={10})
        → LoadCommand(fk_value=project_id, scope_filter=ScopeFilter(ids={10}))
```

### 3.2 Step 1：权限系统查询

**输入** — `user_id` + `action`，无需显式传入 scope_desc。

ScopeComputeView 通过 AutoLoad 自动遍历权限实体链（UserRole → Role → RolePermission → Permission），收集所有权限后输出 flat dict。

**输出** — `dict[str, ScopeFilter]`，统一为以下形态：

| 形态 | 含义 | 示例 |
|------|------|------|
| `{}` | 无权限 | 用户没有任何匹配的 allow 权限 |
| `{"projects": ScopeFilter(ids={1})}` | 资源级约束 | 只能访问 project 1 |
| `{"departments": ScopeFilter(ids=..., filter_fn=...)}` | ABAC 约束 | 按部门+条件过滤 |
| `{所有key: ScopeFilter(is_all=True)}` | 全局权限 | admin 无约束 |

### 3.3 三态语义

框架层（er_diagram.py `create_resolve_method`）处理三种状态：

| `_user_scope` | dict 中 field_name | 行为 |
|---|---|---|
| 属性不存在 | — | scope 系统未启用，loader 收到原始 fk，无约束 |
| key 存在 | `ScopeFilter(...)` | 使用对应的 ScopeFilter |
| key 缺失 | — | 该层级无权限，`ScopeFilter(ids=frozenset())` 传入 loader，返回空 |

关键代码（`er_diagram.py:579-597`）：

```python
scope_data = getattr(self, '_user_scope', None)
if scope_data is not None:
    scope_filter = resolve_scope_filter(scope_data, fld_name)
    if scope_filter is None:
        scope_filter = _SF(ids=frozenset())  # key 缺失 → 无权限
    key_obj = _LC(fk_value=fk, scope_filter=scope_filter)
return loader.load(key_obj)
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

### 3.5 ER Diagram 与 Scope Field 的关联

三处使用同一个字符串，靠命名约定对齐：

```
Relationship.name          AutoLoad 字段名         _user_scope dict key
       │                        │                       │
  "projects"  ──匹配──→  field_name  ──匹配──→  scope_key "projects"
```

| 来源 | 位置 | 字符串 |
|------|------|--------|
| Relationship.name | `entities.py` | `"projects"` |
| AutoLoad 字段名 | 视图模型类 | `projects: Annotated[...]` |
| ScopeRegistry.scope_key | `scope.py` | `"projects"` |

框架层 `create_resolve_method` 用 AutoLoad 字段名去 dict 取值：

```python
scope_filter = resolve_scope_filter(scope_data, fld_name)
# 等价于 scope_data.get("projects")
```

**当前局限**：无编译期校验保证三处一致。`test_scope_alignment.py` 提供运行时检查。

### 3.6 Step 2-3：Scope 绑定 + Hook 传播

```python
# 绑定 scope 到根对象
scope = await compute_user_scope(user_id=5, action="read")
object.__setattr__(root, '_user_scope', scope)

# Hook 将同一个 dict 引用传播到所有 children
def inject_user_scope(parent, field_name, result):
    user_scope = getattr(parent, '_user_scope', None)
    if user_scope is None:
        return
    items = _get_items(result)
    if items:
        for item in items:
            object.__setattr__(item, '_user_scope', user_scope)
    elif result is not None and hasattr(result, '__dict__'):
        object.__setattr__(result, '_user_scope', user_scope)
```

**关键简化**：所有 children 共享同一个 dict 引用。不需要按 item ID 匹配子 scope，不需要树遍历。
每层通过 `dict.get(自己的字段名)` 取出自己关心的约束。

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
  ScopeRegistry                 → resource_type → scope_key 映射
  权限系统返回                   → flat dict: dict[str, ScopeFilter]
  注入根对象                     → object.__setattr__(root, '_user_scope', dict)
  AutoLoad                      → 读取 scope，约束 Loader（ID 或 filter）
  resolved_hooks                → inject_user_scope（同一个 dict 传播）
  子节点                        → 同一个 dict，按字段名取约束
```

### 4.2 Hook 实现——共享 dict 引用

Hook 不做过滤、不做 ID 匹配，只负责将同一个 dict 引用传播到所有 resolved children：

```python
def inject_user_scope(parent, field_name, result):
    user_scope = getattr(parent, '_user_scope', None)
    if user_scope is None:
        return

    items = _get_items(result)
    if items:
        for item in items:
            object.__setattr__(item, '_user_scope', user_scope)
    elif result is not None and hasattr(result, '__dict__'):
        object.__setattr__(result, '_user_scope', user_scope)
```

**和旧实现的对比**：

| 维度 | 旧实现（树模式） | 新实现（flat dict） |
|------|-----------------|-------------------|
| 传播方式 | 按 item ID 匹配子 scope | 同一个 dict 引用 |
| hook 复杂度 | 需要 scope_map / id_to_children | 几行代码 |
| hook 知道的信息 | 需要知道层级结构 | 不需要知道 |
| _access_scope_tree | 树状结构，per-ID 差异化 | flat dict，共享引用 |

### 4.3 AutoLoad 自动约束

AutoLoad 生成的 resolve 方法自动检查实例上的 `_user_scope`，并通过 `LoadCommand` 传递 scope 约束给 Loader：

```python
# AutoLoad 生成的 resolve 方法（er_diagram.py create_resolve_method）
def resolve_projects(self, loader=Loader(department_projects_loader)):
    fk = getattr(self, 'id')
    key_obj = fk  # 默认

    scope_data = getattr(self, '_user_scope', None)
    if scope_data is not None:
        scope_filter = scope_data.get('projects')  # 按字段名取
        if scope_filter is None:
            scope_filter = ScopeFilter(ids=frozenset())  # key 缺失 → 无权限
        key_obj = LoadCommand(fk_value=fk, scope_filter=scope_filter)

    return loader.load(key_obj)
```

使用者不需要写任何 scope 相关代码，`AutoLoad()` 声明即可：

```python
class UserScopeView(UserEntity):
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
            loader=user_departments_by_scope_loader,
        ),
        Relationship(
            fk='id',
            name='projects',
            target=list[ProjectEntity],
            loader=user_projects_by_scope_loader,
        ),
        Relationship(
            fk='id',
            name='documents',
            target=list[DocumentEntity],
            loader=user_documents_by_scope_loader,
        ),
    ]
    id: int
    name: str

class DepartmentEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='id', name='projects', target=list[ProjectEntity], loader=department_projects_loader)
    ]
    id: int
    name: str

class ProjectEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='id', name='documents', target=list[DocumentEntity], loader=project_documents_loader)
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
    from pydantic_resolve.types import LoadCommand

    scope_filters = []
    for k in keys:
        if isinstance(k, LoadCommand):
            scope_filters.append(k.scope_filter)
        else:
            scope_filters.append(None)

    # 收集所有 ID（batching）
    all_ids = set()
    has_unconstrained = any(sf and sf.is_all for sf in scope_filters)
    for sf in scope_filters:
        if sf and sf.ids:
            all_ids.update(sf.ids)

    if not has_unconstrained and not all_ids:
        return [[] for _ in keys]

    # 查询 + ABAC filter
    stmt = select(Department)
    if not has_unconstrained:
        stmt = stmt.where(Department.id.in_(all_ids))
    for sf in scope_filters:
        if sf and sf.filter_fn:
            stmt = sf.filter_fn(stmt)
            break
    rows = (await session.scalars(stmt)).all()
    obj_map = {d.id: d for d in rows}

    # 按 scope_filter 分配结果
    results = []
    for sf in scope_filters:
        if sf is None:
            results.append([])
        elif sf.is_all:
            results.append(list(obj_map.values()))
        elif not sf.ids:
            results.append([])
        else:
            results.append([obj_map[did] for did in sorted(sf.ids) if did in obj_map])
    return results

# 内层 loader 同理：支持 LoadCommand 中的 scope_filter 约束
async def department_projects_loader(keys):
    ...

# --- Phase 3: Scope 计算 + API 响应 ---

# ScopeRegistry：resource_type → scope_key 映射
scope_registry = ScopeRegistry()
scope_registry.register("department", "departments", DepartmentEntity)
scope_registry.register("project",    "projects",    ProjectEntity)
scope_registry.register("document",   "documents",   DocumentEntity)

# ScopeComputeView：通过 Resolver + AutoLoad 自动遍历权限实体
class ScopeComputeView(BaseModel):
    user_id: int
    action: str = "read"
    user_scope: dict[str, ScopeFilter] = {}

    async def post_user_scope(self, collector=RolePermDedupCollector('all_perms')):
        # 收集所有权限，过滤 effect=allow + action 匹配
        # admin → {e.scope_key: ScopeFilter(is_all=True) for e in scope_registry.entries}
        # scoped → {entry.scope_key: ScopeFilter(ids=...) for each authorized level}
        ...

async def compute_user_scope(user_id: int, action: str = "read") -> dict[str, ScopeFilter]:
    view = ScopeComputeView(user_id=user_id, action=action)
    view = await Resolver(enable_from_attribute_in_type_adapter=True).resolve(view)
    return view.user_scope

# 视图模型
class UserScopeView(UserEntity):
    departments: Annotated[list[DepartmentScopeView], AutoLoad()] = []
    projects: Annotated[list[ProjectScopeView], AutoLoad()] = []
    documents: Annotated[list[DocumentScopeView], AutoLoad()] = []

# FastAPI endpoint
@app.get("/users/{user_id}/scope-tree")
async def get_user_scope_tree(user_id: int = Depends(get_current_user_id)):
    # 1. 计算 scope dict
    scope = await compute_user_scope(user_id, "read")

    # 2. 构建根对象并挂载 scope
    root = UserScopeView(id=user_id, name=user_name)
    object.__setattr__(root, '_user_scope', scope)

    # 3. resolve（AutoLoad 自动约束 + hook 传播 scope）
    result = await Resolver(
        resolved_hooks=[inject_user_scope],
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
│  ① ScopeRegistry 注册 resource_type → scope_key 映射      │
│  ② ScopeComputeView 通过 AutoLoad 自动遍历权限实体         │
│  ③ 输出 flat dict: dict[str, ScopeFilter]                 │
│  ④ 注册 resolved_hook 用于 scope 传播                     │
│                                                          │
│  AutoLoad:                                                │
│  ⑤ 读取实例上的 _user_scope                                │
│  ⑥ dict.get(field_name) 获取 ScopeFilter                  │
│  ⑦ 构建 LoadCommand(fk_value, scope_filter) 约束 Loader   │
│                                                          │
│  resolved_hooks:                                          │
│  ⑧ 将同一个 dict 引用传播到 resolved children              │
│                                                          │
│  Entity 不知道 │ Loader 不知道 │ 使用者不知道 │ 前端不知道 │
└──────────────────────────────────────────────────────────┘
```

Loader 接受 scope 约束，和接受 PageArgs 分页参数是同一件事——**都是获取数据时的范围限制，不感知来源。**

---

## 六、Scope 的形态与 ABAC 覆盖

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

### 6.2 Flat Dict 三态语义

`_user_scope` 属性和 dict 中 key 的组合形成三种状态：

| `_user_scope` | dict 中 field_name | AutoLoad 行为 | Loader 收到 |
|---|---|---|---|
| 属性不存在 | — | 无 scope 系统 | 原始 fk 值 |
| key 存在 | `ScopeFilter(...)` | 按 ScopeFilter 约束 | `LoadCommand(fk, scope_filter)` |
| key 缺失 | — | 无权限 | `LoadCommand(fk, ScopeFilter(ids=frozenset()))` |

ScopeFilter 内部维度：

| 维度 | 含义 | Loader 行为 |
|------|------|------------|
| `is_all=True` | 全局权限 | 无约束加载 |
| `ids=frozenset({1,3})` | RBAC 精确 ID | `WHERE id IN (1, 3)` |
| `ids=frozenset()` | 无权限 | 返回空 |
| `filter_fn=callable` | ABAC 条件 | 闭包 append 到 query |

**Filter 以闭包形式传递，在权限系统内部捕获用户上下文：**

```python
# 权限系统内部，捕获 user context 创建闭包
def compute_scope(user, action):
    return {
        "documents": ScopeFilter(
            filter_fn=lambda q: q.filter(Document.classification_level <= user.clearance_level)
        )
    }

# DataLoader 端，只调用闭包，不知道 user context
def batch_load_fn(keys):
    query = select(Document)
    if scope_filter and scope_filter.filter_fn:
        query = scope_filter.filter_fn(query)  # 闭包调用
    return query.all()
```

- **DataLoader 不知道 user context**——闭包已捕获
- **类型安全**——用 ORM 方法而非裸 SQL，避免注入
- **可测试**——闭包可以独立测试
- **数据库无关**——闭包内部用 ORM 抽象

**ScopeFilter 的限制：**
- **不跨进程**：闭包无法序列化，scope dict 仅在单进程内使用
- **DataLoader batching 兼容**：同一批次内共享同一个 ScopeFilter，闭包对所有 key 统一 apply

### 6.3 ABAC 场景覆盖分析

权限系统内部将 RBAC/ABAC 规则翻译为对应的 ScopeFilter：

| ABAC 场景 | 权限系统输出 | filter 能覆盖 |
|-----------|-------------|--------------|
| 部门归属 | `ScopeFilter(ids={1,2})` | 能 |
| 资源密级 | `ScopeFilter(filter_fn=lambda q: q.filter(level <= user.clearance))` | 能 |
| 所有者 | `ScopeFilter(filter_fn=lambda q: q.filter(created_by == user.id))` | 能 |
| 审批状态流转 | 复杂 OR 条件闭包 | 能，但复杂 |
| 时间窗口 | `ScopeFilter(filter_fn=lambda q: q.filter(effective_date <= func.now()))` | 能 |
| 地域合规 | 非 EU 用户：filter 闭包；EU 用户：`is_all=True` | 能 |
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

1. ~~**权限树未覆盖分支的处理**~~：已决——scope 只包含有显式授权的分支，未覆盖的部分默认拒绝
2. ~~**Loader key 替换的时机**~~：已决——AutoLoad 自动读取 scope 约束 Loader
3. ~~**scope 数据结构**~~：已决——从 `list[ScopeNode]` 树简化为 `dict[str, ScopeFilter]` flat dict
4. **scope 缓存**：同一用户短时间内的 scope 可复用
5. **Allow/Deny 跨层级传播**：flat dict 模式下，deny 如何表达？（当前只有 allow 语义）
6. **scope_key 与 Relationship.name 的对齐**：当前靠命名约定，无编译期校验。`test_scope_alignment.py` 提供运行时检查，但应考虑从 ER Diagram 自动推导
7. **根层 FK 语义**：User entity 的 `fk='id'` 是形式上的 FK，实际查询使用 scope_filter.ids。需要评估是否需要在 Relationship 中增加 `scope_driven=True` 标记来区分
8. **GraphQL scope 集成**：GraphQL 查询 AST 已天然包含查询结构，scope 计算可直接复用。需要验证 GraphQLHandler + scope 的集成路径
9. **ScopeRegistry 位置**：当前在 demo 代码中，是否应进入框架核心？如果进入框架核心，注册时机和方式需要设计

---

## 九、现有参考实现

- `demo/rbac/` — RBAC/ABAC demo（含 scope 预计算模式）
  - `entities.py`：资源实体（User/Department/Project/Document）+ 权限实体（Permission/RolePermission/Role/UserRole/GroupRole/MailGroup）的 ER Diagram 定义
  - `loaders.py`：scope-aware loaders（`user_departments_by_scope_loader`, `user_projects_by_scope_loader`, `user_documents_by_scope_loader`）+ 内层 loaders（`department_projects_loader`, `project_documents_loader`）
  - `scope.py`：`ScopeRegistry`（resource_type → scope_key 映射）+ `compute_user_scope`（Resolver + AutoLoad 驱动）+ `inject_user_scope`（resolved_hook，共享 dict 传播）
  - `condition.py`：命名条件注册表（`ConditionDef` + `build_scope` 返回 `(ids, filter_fn)` 元组）
  - `schemas.py`：UserScopeView 使用 AutoLoad + scope 的完整示例（含 departments/projects/documents 三层）
  - `demo.py`：Scenario 6 — Eve（scoped）、Alice（global admin）、Bob（global manager）三个用户的完整 demo
- `pydantic_resolve/graphql/pagination/` — 分页注入机制（scope 的同构参考）
  - `injector.py`：inject_nested_pagination 的实现
  - `types.py`：PageArgs / PageLoadCommand 的定义
- `pydantic_resolve/types.py` — `ScopeFilter`, `LoadCommand` 核心类型（`ScopeNode` 已删除）
- `pydantic_resolve/utils/er_diagram.py` — `create_resolve_method`（AutoLoad scope 处理逻辑）+ `resolve_scope_filter` helper
- `tests/graphql/test_access_scope.py` — flat dict scope 单元测试 + 端到端测试
- `tests/graphql/test_pagination.py` — 分页 + scope 组合测试
- `tests/test_scope_alignment.py` — ScopeRegistry 与 AutoLoad chain 一致性检查

---

## 十、实现状态与架构演进

> 记录架构从初始设计到当前实现的演进路径。

### 10.1 演进历程

```
v1: dict-keyed scope 树
    {'departments': [{'id': 1, 'projects': [{'id': 2}]}]}
    → 问题：per-ID 子树匹配复杂，hook 需要 scope_map

v2: ScopeNode dataclass
    [ScopeNode(type='departments', ids=[1], children=[ScopeNode(type='projects', ids=[2])])]
    → 问题：仍有树遍历，hook 按 ID 匹配子 scope，全局权限需 'all'/'empty' sentinel

v3: flat dict (当前实现)
    {"departments": ScopeFilter(is_all=True), "projects": ScopeFilter(ids={1,3})}
    → 解决：共享 dict 引用，hook 几行代码，每层按字段名取约束
    → 关键认知：权限不需要组装成树，Resolver 的遍历自然产生层级
```

### 10.2 v2 → v3 变更摘要

| 维度 | v2 (ScopeNode) | v3 (flat dict) |
|------|---------------|----------------|
| 数据结构 | `list[ScopeNode]` 树 | `dict[str, ScopeFilter]` |
| 隐藏属性 | `_access_scope_tree` | `_user_scope` |
| Hook | `inject_access_scope` (按 ID 匹配子 scope) | `inject_user_scope` (共享引用) |
| Hook 代码量 | ~50 行 | ~10 行 |
| scope 计算 | `compute_scope_tree` → `list[ScopeNode]` | `compute_user_scope` → `dict[str, ScopeFilter]` |
| 映射注册 | `HIERARCHY` / `SCOPE_ENTRY_ENTITIES` | `ScopeRegistry` |
| 全局权限 | `'all'` sentinel | `{key: ScopeFilter(is_all=True) for all keys}` |
| 无权限 | `'empty'` sentinel | `{}` |
| 框架层查找 | `resolve_scope_filter(scope_tree, field_name)` 遍历 ScopeNode | `scope_data.get(field_name)` 直接取值 |
| 已删除类型 | — | `ScopeNode`, `HierarchyLevel`, `HIERARCHY`, `SCOPE_ENTRY_ENTITIES` |

### 10.3 变更文件

| 文件 | v2 → v3 变更 |
|------|-------------|
| `pydantic_resolve/types.py` | 删除 `ScopeNode` dataclass |
| `pydantic_resolve/utils/er_diagram.py` | `resolve_scope_filter` 简化为 `dict.get()`；scope 读取改为 `_user_scope` |
| `pydantic_resolve/graphql/response_builder.py` | 同上 |
| `demo/rbac/scope.py` | `ScopeRegistry` 替代 `HIERARCHY`；flat dict 输出；`inject_user_scope` 替代 `inject_access_scope` |
| `demo/rbac/demo.py` | 调用 API 更新为 `compute_user_scope` + `_user_scope` |
| `tests/graphql/test_access_scope.py` | 重写为 dict 模式 |
| `tests/graphql/test_pagination.py` | 更新 ScopeNode 相关测试为 dict |
| `tests/test_scope_alignment.py` | 从验证 `HIERARCHY` 改为验证 `ScopeRegistry` 与 AutoLoad chain |

### 10.4 命名条件系统（condition.py）

文档正文未展开描述，实际已实现：

- `ConditionDef` dataclass：`evaluate(subject_attrs, resource_attrs) → bool` + `build_scope(subject_attrs) → (ids, filter_fn)`
- `REGISTRY` 注册表 + `register()` / `get_condition()`
- 三个预定义条件：`same_dept`, `same_dept_non_confidential`, `public_internal_only`
- `build_scope` 返回 `(ids, filter_fn)` 元组——ids 用于 RBAC ID 约束，filter_fn 用于 ABAC filter 闭包

这是 ABAC 场景的核心扩展点。

### 10.5 权限实体的 ER Diagram 声明

`entities.py` 包含 6 个权限实体，与 4 个资源实体共享同一个 `BaseEntity = base_entity()`：

```
PermissionEntity (leaf)
RolePermissionEntity → permission → PermissionEntity
RoleEntity → role_permissions → list[RolePermissionEntity]
UserRoleEntity → role → RoleEntity
GroupRoleEntity → role → RoleEntity
MailGroupEntity (leaf)
```

### 10.6 compute_user_scope 从 raw SQL 重构为 AutoLoad 驱动

`ScopeComputeView` 不直接操作数据库，通过 AutoLoad 遍历权限实体链：

```
ScopeComputeView
  → resolve_user_roles → UserRoleEntity → ScopeUserRoleView
    → role → RoleEntity → ScopeRoleView
      → role_permissions → RolePermissionEntity → ScopeRolePermView
        → permission → PermissionEntity
  → resolve_group_roles → GroupRoleEntity → ScopeGroupRoleView
    → role → (同上)
  → post_user_scope → RolePermDedupCollector 汇总 → 输出 dict[str, ScopeFilter]
```

层级关系不再硬编码在 `_build_scope_nodes` / `_build_project_nodes` 中。
ScopeRegistry 管理映射，`_build_resource_scope` 遍历 registry entries。
