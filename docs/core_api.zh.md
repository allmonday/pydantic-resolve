# Core API

[English](./core_api.md) | [docs](./index.zh.md)

上一页只展示了“一个字段从当前节点之外拿数据”。这一页把同一个思路扩展到一棵嵌套响应树。

这里仍然只讲手写组装模型。不引入 ERD，不引入 `AutoLoad`。只使用普通的 `resolve_*` 方法、批量 loader，以及 resolver 的递归遍历。

## 从一个字段扩展到一棵树

现在我们想要的 sprint 响应结构是：

- `Sprint` 有多个 `tasks`
- 每个 `Task` 有一个 `owner`

于是整个数据树就变成了：`Sprint -> Task -> User`。

## 完整示例

```python
from typing import List, Optional

from pydantic import BaseModel
from pydantic_resolve import Loader, Resolver, build_list, build_object


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


async def task_loader(sprint_ids: list[int]):
    tasks = await db.query(Task).filter(Task.sprint_id.in_(sprint_ids)).all()
    return build_list(tasks, sprint_ids, lambda task: task.sprint_id)


class SprintView(BaseModel):
    id: int
    name: str
    tasks: List[TaskView] = []

    def resolve_tasks(self, loader=Loader(task_loader)):
        return loader.load(self.id)


sprints = [SprintView.model_validate(sprint) for sprint in raw_sprints]
sprints = await Resolver().resolve(sprints)
```

## `build_list` 的职责

`user_loader` 用 `build_object(...)`，因为一个 user id 只对应一个 user。

`task_loader` 用 `build_list(...)`，因为一个 sprint id 对应的是一组 task。

```python
return build_list(tasks, sprint_ids, lambda task: task.sprint_id)
```

这行代码会先按 `sprint_id` 分组，再按输入的 `sprint_ids` 顺序返回结果。

## Resolver 是如何递归工作的

关键点在于：你不需要写任何手动遍历逻辑。不需要嵌套循环，也不需要单独写 orchestration 层来安排“先查 task，再查 owner”。

Resolver 会自动处理这个顺序：

1. 先加载 `SprintView.tasks`
2. 再检查返回的每个 `TaskView`
3. 继续加载 `TaskView.owner`
4. 一直递归，直到没有未解析字段为止

这就是 Core API 比 endpoint 级胶水代码更容易维护的原因。

## 什么时候继续手写 `resolve_*` 就够了

以下场景里，手写 Core API 往往已经足够：

- 响应模型还不多
- 关系声明还没有开始重复
- 你希望每个接口保持显式可读
- 响应结构还在快速变化，不值得先抽象

在这个阶段，显式本身就是优点。

## 这一页刻意还没讲什么

到这里我们只是在加载关联数据，还没有计算派生字段，比如：

- `task_count`
- `contributor_names`

这些属于下一个概念层。

## 下一步

继续读 [Post Processing](./post_processing.zh.md)，看一个字段什么时候应该在整棵子树装配完成之后再计算。