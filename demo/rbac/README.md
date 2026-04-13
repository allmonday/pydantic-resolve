# RBAC/ABAC Demo

Demonstrates pydantic-resolve + SQLAlchemy with three resource tables
(departments, projects, documents) and FK-based ancestor tracing for
permission inheritance. Includes mail group support via third-party API.

## Architecture

```
User ── user_departments ──► Department
  │
  ├── user_roles ──► Role ── role_permissions ──► Permission
  │              ▲                                   │
  │              │                                   │
  │(depts,level) │                                   │ (resource_type, action, effect)
  │              │                                   │ conditions (JSONB)
  │         group_roles                              │
  │              │                                   │
  └──(3rd API)── MailGroup                           │
                                                   ┌─▼──────────┐
  Departments ◄── Projects ◄── Documents           │RolePermission│
  (id,name,      (dept_id FK,  (project_id FK,     │ resource_type│
   owner,vis)     owner,vis)    dept_id,owner,vis)  │ resource_id  │
                                                   └─────────────┘
```

### Data Model

**Core entities:**

| Table | Key Fields | Description |
|-------|-----------|-------------|
| User | id, name, email, level | level 用于 ABAC 条件比较 |
| Department | id, name, owner_id, visibility | 顶级资源，无父节点 |
| Project | id, name, department_id (FK), owner_id, visibility | 二级资源，归属部门 |
| Document | id, name, project_id (FK), department_id, owner_id, visibility | 三级资源，归属项目 |

**授权相关:**

| Table | Key Fields | Description |
|-------|-----------|-------------|
| Role | id, name | admin / manager / viewer |
| Permission | id, name, action, resource_type | action: read/write/delete/admin/export; resource_type: `*` 或具体类型 |
| RolePermission | role_id, permission_id, resource_type, resource_id, effect, conditions | 关联角色与权限，附带 ABAC 条件 (JSON) |
| UserRole | user_id, role_id | 用户直接角色分配 |
| GroupRole | group_id, role_id | 邮件组 → 角色映射 |

**种子数据 (4 个用户):**

| User | Departments | Direct Roles | Mail Groups |
|------|------------|--------------|-------------|
| Alice (level=3) | Engineering, Marketing | admin, manager | engineering-all |
| Bob (level=2) | Engineering | manager | engineering-all, eng-leads |
| Charlie (level=2) | Marketing | manager | marketing-all |
| Diana (level=1) | Marketing | viewer | marketing-all |

### Ancestor Tracing (no closure table)

Instead of a pre-computed closure table, ancestor tracing uses sequential FK
lookups: `document.project_id → project.department_id`. Since the hierarchy is
only 3 levels deep, this requires at most 2 queries — no recursive CTE needed.

```
document(id=1) → project_id=1 → department_id=1
                   project(id=1) → department_id=1
                                     department(id=1)
Ancestors of document#1: {(document,1), (project,1), (department,1)}
```

When checking permissions for a document, the system looks for RolePermissions
attached to any ancestor. This means a permission on `department(id=1)` also
applies to all projects and documents under it.

### Permission Resolution: Two Sources Merged

```
Direct:   User → UserRole → Role → RolePermission → Permission
Group:    User → MailGroup (3rd party API) → GroupRole → Role → RolePermission → Permission
          ─────────────────────────────────────────────────────────────────────────
          Both merged in candidate_permissions_loader → ABAC fine filter in post_*
```

`candidate_permissions_loader` 同时查询两条路径，将直接角色权限和邮件组继承权限合并为一组
candidate permissions。后续 ABAC 精细过滤不区分来源，统一处理。

### ABAC Condition Evaluation

```
SQL (DataLoader)                      Python (post_*)
─────────────────                     ────────────────
1. Trace ancestors via FK lookups     evaluate_conditions()
2. JOIN user_roles / group_roles      compare subject attrs
3. JOIN role_permissions              with resource attrs
4. WHERE action IN (?, 'admin')      → True / False
→ candidate permissions
```

ABAC 条件存储在 `RolePermission.conditions` 字段 (JSON)，格式示例：

```json
{
  "and": [
    {"field": "resource.department_id", "op": "in", "value": "subject.department_ids"},
    {"field": "resource.visibility", "op": "neq", "value": "confidential"}
  ]
}
```

- `field` 和 `value` 支持 `subject.xxx` / `resource.xxx` 引用
- 支持的操作符: eq, neq, gt, lt, gte, lte, in
- 支持 `and` / `or` 逻辑组合
- `conditions=None` 表示无条件放行

**权限判断流程 (post_accessible):**

1. 遍历 candidate_perms
2. 跳过 `effect != "allow"` 的规则
3. 若 `conditions=None`，直接放行
4. 若有 conditions，调用 `evaluate_conditions()` 比较 subject 和 resource 属性
5. 返回第一条匹配的 allow 规则；若无匹配则拒绝

### pydantic-resolve 使用模式

本 demo 展示了 pydantic-resolve 的核心能力：

**resolve_\* — DataLoader 批量加载:**
```python
class RoleWithPerms(BaseModel):
    id: int
    name: str
    permissions: list[PermissionView] = []

    def resolve_permissions(self, loader=Loader(role_permissions_loader)):
        return loader.load(self.id)
```

**post_\* — ABAC 精细过滤:**
```python
class ResourceAccessView(BaseModel):
    candidate_perms: list[CandidatePerm] = []
    accessible: bool = False

    def post_accessible(self, ancestor_context=None):
        # 在 candidate_perms 加载完成后，评估 ABAC 条件
        ...
```

**ExposeAs — 向子节点传递上下文:**
```python
class AccessCheckRequest(BaseModel):
    user_id: Annotated[int, ExposeAs("check_user_id")]
    action: Annotated[str, ExposeAs("check_action")]
```

## Run

```bash
uv run python -m demo.rbac.demo
```

## Scenarios

### Scenario 1: User Permission Expansion (Dashboard)

展示 4 个用户的完整权限展开: User → Roles → Permissions。

**执行流程:**
1. 构建 4 个 `UserPermissionView` 实例
2. `resolve_department_ids`: DataLoader 批量加载所有用户部门 (1 条 SQL)
3. `resolve_roles`: DataLoader 批量加载所有用户角色 (1 条 SQL)
4. `resolve_permissions`: DataLoader 批量加载所有角色权限 (1 条 SQL)
5. 总计: 3 条 SQL (对比 N+1 场景下需要 1+4+4+... 条)

### Scenario 2: ABAC Condition Evaluation

13 个测试用例验证条件权限判断，涵盖:
- 同部门读写 (Bob → Design Doc)
- 跨部门拒绝 (Charlie → Design Doc)
- 可见性限制 (Diana → Budget Plan / confidential)
- resource_type 范围限制 (export_doc 只对 document 生效)

**执行流程:**
1. `AccessCheckRequest` 通过 ExposeAs 向子节点传递 user_id, action 等上下文
2. `resolve_resources`: 批量加载目标资源
3. `resolve_candidate_perms`: DataLoader 执行 SQL 粗筛 (祖先追溯 + action 匹配)
4. `post_accessible`: Python 侧精细过滤 (ABAC 条件评估)

### Scenario 3: Resource Hierarchy (Dept → Project → Document)

三层资源树的遍历加载。

**执行流程:**
1. 构建 2 个 `DepartmentNode` 实例
2. `resolve_projects`: DataLoader 批量加载所有部门的项目 (1 条 SQL)
3. `resolve_documents`: DataLoader 批量加载所有项目的文档 (1 条 SQL)
4. 总计: 2 条 SQL (对比 N+1 需要 1+2+4+... 条)

### Scenario 4: Batch Permission Check (List View)

一次性检查某用户对所有文档的 read/write 权限。

**执行流程:**
1. `DocumentListView` 通过 ExposeAs 传递 user context
2. `resolve_documents`: 加载全部文档
3. 每个 `DocumentWithAccess` 的 `resolve_candidate_perms` 批量加载权限
4. `post_can_read` / `post_can_write` 分别评估读写权限
5. 所有 N 个文档的权限检查合并为 1 次 candidate_permissions_loader 调用

### Scenario 5: Mail Group Permission Inheritance

展示邮件组继承权限的效果。

**Bob 的权限来源:**
- 直接: manager 角色 (来自 user_roles)
- 邮件组: engineering-all → manager, eng-leads → admin

eng-leads 组赋予了 Bob admin 权限，使他能跨过 confidential 限制写 Project Beta。

**candidate_permissions_loader 内部流程:**
1. 追踪资源祖先
2. 查询直接角色权限 (UserRole JOIN RolePermission JOIN Permission)
3. 调用第三方 API 获取用户邮件组
4. 查询邮件组角色权限 (GroupRole JOIN RolePermission JOIN Permission)
5. 合并去重后返回

| Scenario | Description | SQL Queries | N+1 Equivalent |
|----------|-------------|-------------|----------------|
| 1. Dashboard | User→Roles→Permissions expansion | 3 | 1+4+4+... |
| 2. ABAC Check | Condition-based access evaluation | 2 per check | N per check |
| 3. Hierarchy | Dept→Project→Document tree | 2 | 1+2+4+... |
| 4. Batch Check | N documents × permission check | 2 | 1+2N |
| 5. Mail Groups | Group-inherited permissions via 3rd party API | 3 | varies |

## Files

- `models.py` — SQLAlchemy ORM models (10 tables: Department, Project, Document, UserDepartment, etc.)
- `database.py` — SQLite async setup + seed data
- `condition.py` — ABAC condition evaluation engine
- `loaders.py` — DataLoader batch functions with ancestor tracing
- `schemas.py` — Pydantic models with resolve_*/post_* methods
- `mailgroup_api.py` — Mock third-party mail group API
- `demo.py` — Main script demonstrating all scenarios
