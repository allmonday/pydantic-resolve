# GraphQL and MCP

[English](./graphql_and_mcp.md) | [docs](./index.zh.md)

当 ERD 建好之后，GraphQL 和 MCP 就会变成“复用层”。它们建立在同一份模型图之上，而不是要求你再学第二套数据组装体系。

要记住的 framing 是：GraphQL 与 MCP 是 ERD 的下游能力，不是 Core API 的替代品。

## GraphQL：在同一张图上增加根入口

上一页中的关系定义不需要变。为了通过 GraphQL 暴露它们，你只需要补上根查询或变更。

```python
from pydantic import BaseModel
from pydantic_resolve import GraphQLHandler, Relationship, base_entity, query


BaseEntity = base_entity()


class UserEntity(BaseModel, BaseEntity):
    id: int
    name: str


class TaskEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='owner_id', target=UserEntity, name='owner', loader=user_loader)
    ]
    id: int
    title: str
    owner_id: int


class SprintEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(fk='id', target=list[TaskEntity], name='tasks', loader=task_loader)
    ]
    id: int
    name: str

    @query(name='sprints')
    async def get_all(cls, limit: int = 20) -> list['SprintEntity']:
        return await fetch_sprints(limit)


diagram = BaseEntity.get_diagram()
handler = GraphQLHandler(diagram)

result = await handler.execute(
    """
    {
      sprints {
        id
        name
        tasks {
          id
          title
          owner {
            id
            name
          }
        }
      }
    }
    """
)
```

### 一个实用说明

实际的 GraphQL 根字段名来自你的 `@query(...)` 或 `QueryConfig(...)` 配置。这里真正重要的点不是装饰器本身，而是嵌套关系图仍然来自同一份 ERD。

如果你更喜欢外部配置而不是装饰器，也可以用 `QueryConfig` 和 `MutationConfig` 在类之外定义相同的根操作。

## MCP：继续复用同一层 GraphQL 能力

MCP 支持建立在 GraphQL 这一层之上。

```python
from pydantic_resolve import AppConfig, create_mcp_server


mcp = create_mcp_server(
    apps=[AppConfig(name='agile', er_diagram=diagram)]
)
mcp.run()
```

如果需要 MCP 支持，安装可选依赖：

```bash
pip install pydantic-resolve[mcp]
```

这里真正的重点是架构复用：

- 业务关系只维护在一份 ERD 中
- GraphQL 把它暴露给结构化客户端
- MCP 再把它暴露给 AI agent 和工具

## 这一页并不是在说什么

这一页不是在建议所有用户都从 GraphQL 或 MCP 开始。最好的入门入口依然是 Core API，因为它直接教会你数据是如何被组装出来的。

只有当 ERD 已经稳定提供关系知识时，GraphQL 与 MCP 的复用价值才真正出现。

## 下一步

继续读 [Reference Bridge](./reference_bridge.zh.md)，看看主学习路径结束后推荐如何继续阅读。