# Reference Bridge

[English](./reference_bridge.md) | [docs](./index.zh.md)

`docs/` 主路径到这里结束。接下来读者通常会进入两类需求之一：

- 想看更细的 API 细节
- 想了解更大的项目背景与外围资料

这些需求都合理，但它们与 onboarding 不是同一种阅读目标。所以它们应该放在第一次阅读路径之外。

## 接下来去哪里

| 需求 | 下一步阅读 | 原因 |
|---|---|---|
| 查看完整 API 面 | `docs_old/api.md` | 构造参数、工具函数、loader 元数据、底层行为等细节都在这里 |
| 版本升级 | `docs/migration.md` | 迁移很重要，但不应该挤进核心教学路径 |
| 查看发布历史 | `docs/changelog.md` | 更适合已经理解概念之后再看 |
| 理解项目动机 | `docs/why.md` | 解释这个库为什么存在、背后的权衡是什么 |
| UI / SDK 集成 | `docs/connect_to_ui.md` | 更偏 OpenAPI 与客户端集成问题 |

## 一个推荐的二次阅读顺序

如果你已经读完主路径，下面这个顺序通常最有效：

1. API reference
2. migration guide
3. GraphQL framework 细节
4. 项目动机
5. UI 集成说明

## 目前仍然留在 `docs_old/` 中的内容

当前尚未迁移的 reference 型资料仍然保留在 `docs_old/` 中。`docs/` 这一轮的重点是先把新的渐进式学习路径建立起来。

所以现在可以这样理解：

- `docs/` 是新的教程路径
- `docs_old/` 仍然承载较早的参考型和主题型资料

## 以后可能继续迁移的主题

后续版本的 `docs/` 还可以继续吸收和重构这些主题：

- 继承与复用模式
- 各种框架的集成指南
- API 参考的进一步整理

但这些内容应该在主路径已经稳定之后再移动。