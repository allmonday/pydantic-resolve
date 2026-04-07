# 旧文档映射

[English](./source_mapping.md) | [docs](./index.zh.md)

这个页面说明了早期 `docs_old/` 文档到当前 `docs/` 结构的对应关系。原本重叠的内容已被收敛为一条更清晰的渐进式学习路径。

## 主路径映射

| 现有来源 | docs 目标页 | 动作 | 说明 |
|---|---|---|---|
| `README.md` | 所有主路径页面 | 拆分吸收 | 主要提供节奏、scenario 连续性、概念顺序 |
| `README.zh.md` | 所有 `.zh.md` 主路径页面 | 拆分吸收 | 新路径中文表述的重要参考来源 |
| `docs_old/install.md` | `quick_start.md` | 折叠进来 | 安装应紧贴第一次价值出现 |
| `docs_old/introduction.md` | `quick_start.md`、`core_api.md`、`erd_and_autoload.md` | 拆分 | 旧页混合了动机、核心模型和 ERD |
| `docs_old/dataloader.md` | `quick_start.md`、`core_api.md` | 拆分 | N+1、batching 与 `build_*` 应前置 |
| `docs_old/expose_and_collect.md` | `cross_layer_data_flow.md` | 重写 | 保留概念，统一 scenario |
| `docs_old/erd_driven.md` | `erd_and_autoload.md` | 重写并压缩 | 保留 ERD 规模化主线，移除旁支 |
| `docs_old/schema_first.md` | `erd_and_autoload.md` | 合并 | 不再作为主路径中的独立站点 |
| `docs_old/graphql.md` | `graphql_and_mcp.md` | 重新 framing | 作为 ERD 的复用层来讲，而不是独立入口 |

## 补充材料映射

| 现有来源 | 目标角色 | 动作 | 说明 |
|---|---|---|---|
| `docs_old/api.md` | reference | 先保留在外部 | 仍然适合作为参考文档 |
| `docs_old/migration.md` | reference | 已复制到 `docs/` | 重要参考页，现已并入新路径 |
| `docs_old/changelog.md` | reference | 已复制到 `docs/` | 历史记录现已并入新路径 |
| `docs_old/why.md` | supplemental | 后续桥接 | 动机不应该打断 onboarding |
| `docs_old/connect_to_ui.md` | supplemental | 后续桥接 | 对集成有帮助，但不属于核心学习 |
| `docs_old/use_case.md` | appendix 候选 | 选择性吸收 | 更适合做定位补充，不适合做主线 |
| `docs_old/inherit_reuse.md` | 后续高级页 | 延后 | 主路径稳定前不应提前进入 |

## 各页来源对照

| docs 页面 | 主要来源 | 改写目标 |
|---|---|---|
| `index.md` | `README.md`、`mkdocs.yml` | 解释新的阅读顺序与边界 |
| `scenario_contract.md` | `README.md`、`README.zh.md` | 固定命名、scenario 与术语 |
| `quick_start.md` | `README.md`、`docs_old/install.md`、`docs_old/dataloader.md` | 用一个 N+1 问题给出第一次价值 |
| `core_api.md` | `README.md`、`docs_old/introduction.md`、`docs_old/dataloader.md` | 从一个字段扩展到一棵嵌套树 |
| `post_processing.md` | `README.md` | 解释 `post_*` 的时机与职责 |
| `cross_layer_data_flow.md` | `README.md`、`docs_old/expose_and_collect.md` | 保留概念，统一例子 |
| `erd_and_autoload.md` | `README.md`、`docs_old/erd_driven.md`、`docs_old/schema_first.md` | 把 ERD 定位为规模化步骤 |
| `graphql_and_mcp.md` | `README.md`、`docs_old/graphql.md` | 展示同一张图的复用 |
| `reference_bridge.md` | `docs_old/api.md`、`docs_old/migration.md`、`docs_old/why.md`、`docs_old/connect_to_ui.md` | 明确教程路径在何处结束 |

## 这页应该怎么使用

这页提供了旧主题式拆分与当前渐进式路径之间的映射表。当你需要追溯某个主题被迁移到了哪里，或者在同步翻译时，可以参考它。