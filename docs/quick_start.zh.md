# Quick Start

[English](./quick_start.md) | [docs](./index.zh.md)

这一页只解决一个接口级问题：每个 task 上有 `owner_id`，但响应模型需要暴露完整的 `owner` 对象。

如果你当前只是想修几个接口里的 N+1 问题，那么读完这一页和下一页，通常就已经够用了。

## 问题是什么

假设你的 task 列表接口起始数据长这样：

```python
raw_tasks = [
    {"id": 10, "title": "Design docs", "owner_id": 7},
    {"id": 11, "title": "Refine examples", "owner_id": 8},
]
```

但你真正想要的响应契约不是只有 `owner_id`，而是：

```json
{
  "id": 10,
  "title": "Design docs",
  "owner": {
    "id": 7,
    "name": "Ada"
  }
}
```

最直接的写法往往是循环 task，然后为每个 task 单独查一次 owner。这正是 pydantic-resolve 想消除的 N+1 场景。

## 安装

```bash
pip install pydantic-resolve
```

如果后面还想用 MCP：

```bash
pip install pydantic-resolve[mcp]
```

## 最小可用示例

```python
from typing import Optional

from pydantic import BaseModel
from pydantic_resolve import Loader, Resolver, build_object


class UserView(BaseModel):
    id: int
    name: str


async def user_loader(user_ids: list[int]):
    users = await db.query(User).filter(User.id.in_(user_ids)).all()
    return build_object(users, user_ids, lambda user: user.id)


class TaskView(BaseModel):
    id: int
    title: str
    owner_id: int
    owner: Optional[UserView] = None

    def resolve_owner(self, loader=Loader(user_loader)):
        return loader.load(self.owner_id)


tasks = [TaskView.model_validate(task) for task in raw_tasks]
tasks = await Resolver().resolve(tasks)
```

## 这段代码里每一部分的职责

- `owner` 初始值是 `None`，因为根数据里并没有完整 owner 对象
- `resolve_owner` 用来声明这个缺失字段该怎么获取
- `Loader(user_loader)` 声明的是批量依赖，不是立刻执行查询
- `Resolver().resolve(tasks)` 会遍历模型树，发现并执行 `resolve_*`

## 为什么 `build_object` 很重要

`user_loader` 接收到的是一组 key，而不是单个 key，所以它必须按输入顺序返回结果。

```python
return build_object(users, user_ids, lambda user: user.id)
```

这行代码的作用，就是把无序的 `users` 集合整理成与 `user_ids` 一一对齐的结果列表。

## 为什么这能消除 N+1

假设列表里有 100 个 task，resolver 并不会调用 100 次 `user_loader`。它会：

1. 先收集所有被请求到的 `owner_id`
2. 用整批 id 调用一次 `user_loader`
3. 再把结果映射回正确的 `TaskView.owner`

这就是这个库最核心的价值，而且这是它最小的工作形态。

## 最好用的第一层心智模型

> `resolve_*` 的含义就是：这个字段需要从当前节点之外拿数据。

后面所有能力，都是在这个模型之上继续展开。

## 什么时候停在这里就够了

下面这些情况，停在这一层完全合理：

- 你只需要修几个关联字段
- 响应模型还在快速变化
- 关系定义还没有在多个模型间重复出现

## 下一步

继续读 [Core API](./core_api.zh.md)，把同样的模式从一个字段扩展到整棵嵌套树：`Sprint -> Task -> User`。