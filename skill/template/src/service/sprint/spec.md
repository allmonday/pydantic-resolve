# SprintService

## 目的

Sprint 管理服务，提供 Sprint 列表查询和详情查询，自动加载下属任务及负责人，并计算派生字段。

## 用途

- 列出所有 Sprint（含任务列表、任务计数、贡献者名单）
- 按 ID 查询单个 Sprint 详情

## 需求

| 方法 | 说明 | 返回 |
|------|------|------|
| `list_sprints` | 获取全部 Sprint，含 tasks + 派生字段 | `list[SprintSummary]` |
| `get_sprint` | 按 ID 获取单个 Sprint | `SprintSummary \| None` |

## DTO

- `SprintSummary` — id, name, task_list(list[TaskEntity]), task_count(post_*), contributor_names(post_*)

## 派生字段

- `task_count` — `post_task_count`，基于已加载的 task_list 计算
- `contributor_names` — `post_contributor_names`，从 task_list 中提取去重排序的 owner name

## 变更记录

| 阶段 | 变更 |
|------|------|
| Phase 3 | 初始创建，实现 list_sprints 和 get_sprint |
