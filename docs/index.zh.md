# docs

[English](./index.md)

`docs/` 是 pydantic-resolve 新的渐进式文档路径。它在不改动现有 `docs/` 目录的前提下，围绕同一个 scenario、同一条学习顺序，以及更清晰的页面边界，重建整个阅读体验。

核心设计原则很简单：先从一个真实的接口级 N+1 问题开始，在同一套业务模型上逐步增加复杂度，只有当手写模型已经足够清楚之后，才引入自动化能力。

## 这条路径主打什么

- 从一个具体问题快速上手
- 全程复用同一个 scenario：`Sprint -> Task -> User`
- 将学习路径与参考资料明确分开
- 将 ERD、GraphQL、MCP 作为规模化与复用能力来介绍，而不是入门入口

## 学习路径

```mermaid
flowchart LR
    a["一个 N+1 问题"] --> b["用 resolve_* 组装嵌套树"]
    b --> c["用 post_* 计算派生字段"]
    c --> d["跨层数据流"]
    d --> e["ERD 与 AutoLoad"]
    e --> f["GraphQL 与 MCP 复用"]
```

## 建议按这个顺序阅读

| 页面 | 主要回答的问题 |
|---|---|
| [Quick Start](./quick_start.zh.md) | 如何用最小可用代码解决一个 N+1 问题？ |
| [Core API](./core_api.zh.md) | 多个 `resolve_*` 方法如何组成一棵嵌套响应树？ |
| [Post Processing](./post_processing.zh.md) | 一个字段什么时候应该写在 `post_*`，而不是 `resolve_*`？ |
| [Cross-Layer Data Flow](./cross_layer_data_flow.zh.md) | 父子节点如何在不手写遍历逻辑的情况下协作？ |
| [ERD and AutoLoad](./erd_and_autoload.zh.md) | 什么时候值得把重复的关系声明提升为 ERD？ |
| [GraphQL and MCP](./graphql_and_mcp.zh.md) | 同一份 ERD 如何继续复用到外部接口？ |
| [Reference Bridge](./reference_bridge.zh.md) | 主学习路径结束后，接下来应该看哪里？ |

## 统一 Scenario

主路径中的每一页都复用同一套业务模型：

- `Sprint` 有多个 `Task`
- `Task` 有一个 `owner`
- `Sprint` 需要派生字段 `task_count` 与 `contributor_names`
- `Sprint` 可以向下暴露 `sprint_name`
- `Task.owner` 可以向上汇总为 `contributors`

完整命名约束见 [Scenario Contract](./scenario_contract.zh.md)。

## 有意放在主路径之外的内容

下面这些内容依然重要，但不应该打断第一次阅读：

- API 参考文档
- 迁移指南
- 变更记录
- 项目动机与来历
- UI 集成细节
- 继承复用等进阶侧主题

这些材料会通过 [Reference Bridge](./reference_bridge.zh.md) 与主路径连接。

## 这个目录与现有文档的关系

`docs/` 主要承载渐进式学习路径，而 `docs_old/` 继续保留尚未迁移的旧版按主题分栏内容。

- `docs/` 更强调 onboarding 与概念顺序
- `docs_old/` 仍然保留较早的参考型和主题型页面
- `docs/` 中英页面采用同一套结构

## 来源材料

第一轮 `docs/` 主要基于原先位于以下位置的材料拆分整理：

- `README.md`
- `README.zh.md`
- `docs_old/introduction.md`
- `docs_old/install.md`
- `docs_old/dataloader.md`
- `docs_old/expose_and_collect.md`
- `docs_old/erd_driven.md`
- `docs_old/schema_first.md`
- `docs_old/graphql.md`

旧文档到新结构的映射见 [Source Mapping](./source_mapping.zh.md)。