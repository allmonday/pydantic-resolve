# TaskService

## 目的

Task 管理服务，提供任务的查询能力，自动加载负责人信息。

## 用途

- 列出所有任务（含 auto-loaded owner）
- 按 Sprint 查询任务列表
- 按 ID 查询单个任务详情

## 需求

| 方法 | 说明 | 返回 |
|------|------|------|
| `list_tasks` | 获取全部任务，含 owner | `list[TaskSummary]` |
| `get_tasks_by_sprint` | 按 Sprint ID 过滤任务 | `list[TaskSummary]` |
| `get_task` | 按 ID 获取单个任务 | `TaskSummary \| None` |

## DTO

- `TaskSummary` — id, title, done, owner_detail(UserSummary via AutoLoad)
- `UserSummary` — id, name

## 变更记录

| 阶段 | 变更 |
|------|------|
| Phase 3 | 初始创建，实现 list_tasks、get_tasks_by_sprint 和 get_task |
