# Scenario 约定

[English](./scenario_contract.md) | [docs](./index.zh.md)

这个文件定义了 `docs/` 主学习路径统一使用的 scenario。主路径里的每一页都应该复用它，这样读者就不需要在不同页面之间反复重建上下文。

## 业务模型

| 实体 | 关键字段 | 在教程中的角色 |
|---|---|---|
| `Sprint` | `id`, `name` | 根响应节点 |
| `Task` | `id`, `title`, `sprint_id`, `owner_id` | 嵌套子节点 |
| `User` | `id`, `name` | 被加载到 `Task.owner` 的关联数据 |

## 统一关系

- `Sprint.id -> Task.sprint_id`
- `Task.owner_id -> User.id`

## 统一响应字段

- `Sprint.tasks`
- `Task.owner`
- `Sprint.task_count`
- `Sprint.contributor_names`
- `Sprint.contributors`
- `Task.full_title`

## 统一 Loader 名称

- `task_loader`
- `user_loader`

## 统一类名

- 手写组装阶段：`UserView`、`TaskView`、`SprintView`
- ERD 阶段：`UserEntity`、`TaskEntity`、`SprintEntity`

## 统一方法名

- `SprintView.resolve_tasks`
- `TaskView.resolve_owner`
- `SprintView.post_task_count`
- `SprintView.post_contributor_names`
- `SprintView.post_contributors`
- `TaskView.post_full_title`

## 统一跨层命名

- Expose 别名：`sprint_name`
- Collector 别名：`contributors`

## 统一示例数据形状

文档里的例子应该尽量从类似这样的数据出发：

```python
raw_sprints = [
    {"id": 1, "name": "Sprint 24"},
    {"id": 2, "name": "Sprint 25"},
]

raw_tasks = [
    {"id": 10, "title": "Design docs", "sprint_id": 1, "owner_id": 7},
    {"id": 11, "title": "Refine examples", "sprint_id": 1, "owner_id": 8},
]
```

示例数据的值可以变，但字段名和关系方向不应该变。

## 示例演进顺序

主路径中的页面应按这个顺序扩展同一个例子：

1. 先加载 `Task.owner`
2. 再加载 `Sprint.tasks`
3. 再计算 `task_count` 与 `contributor_names`
4. 再引入 `sprint_name` 向下传递与 `contributors` 向上收集
5. 再把重复的 `resolve_*` 迁移到 `Relationship` + `AutoLoad`
6. 最后复用同一份 ERD 到 GraphQL 与 MCP

## 术语

- `Resolver` — 遍历与调度的 orchestrator
- `Loader(...)` — `resolve_*` 方法中的依赖声明
- `DataLoader` — 仅在讨论 batching 模式或 `aiodataloader` 时使用
- `ERD` — 应用层的关系定义（不局限于数据库 ER 图）

## 适用范围

主路径中的所有页面统一使用此 scenario。主路径之外的页面（API 参考、迁移说明、变更记录、项目动机等）可以根据主题需要使用不同的例子。