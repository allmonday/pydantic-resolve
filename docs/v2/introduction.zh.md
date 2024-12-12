# 简介

pydantic-resolve 是一个基于 pydantic 的轻量级封装库， 它为 pydantic 和 dataclass 对象添加了 resolve 和 post 方法。

如果你曾经写过类似的代码， 并且觉得不满意， pydantic-resolve 可以派上用场。

```python
story_ids = [s.id for s in stories]
tasks = await get_all_tasks_by_story_ids(story_ids)

story_tasks = defaultdict(list)

for task in tasks:
    story_tasks[task.story_id].append(task)

for story in stories:
    tasks = story_tasks.get(story.id, [])
    story.total_task_time = sum(task.time for task in tasks)
    story.total_done_tasks_time = sum(task.time for task in tasks if task.done)
```

它可以将处理过程根据指责来拆分为描述数据和加载数据两部分， 使数据的组合计算更加清晰可维护

```python
@model_config()
class Story(Base.Story)

    tasks: List[Task] = Field(default_factory=list, exclude=True)
    def resolve_tasks(self, loader=LoaderDepend(TaskLoader)):
        return loader.load(self.id)

    total_task_time: int = 0
    def post_total_task_time(self):
        return sum(task.time for task in self.tasks)

    total_done_task_time: int = 0
    def post_total_done_task_time(self):
        return sum(task.time for task in self.tasks if task.done)
```

它可以在数据组装过程中， 降低获取和调整环节的代码复杂度， 使代码更加贴近 ER 模型， 更加可维护。

借助 pydantic 它可以像 GraphQL 一样用图的关系来描述数据结构， 也能够在获取数据的同时根据业务做调整。

它可以和 FastAPI 轻松合作， 在后端构建出前端友好的数据结构， 以 typescript sdk 的方式提供给前端。

> 在使用面向 ERD 的建模方式下， 它可以为你提供 3 ~ 5 倍的开发效率提升， 减少 50% 以上的代码量。

它为 pydantic 对象提供了 resolve 和 post 方法。

- [resolve](./api.zh.md#resolve) 通常用来获取数据
- [post](./api.zh.md#post) 可以在获取数据后做额外处理

```python hl_lines="13 17"
from pydantic import BaseModel
from pydantic_resolve import Resolver
class Car(BaseModel):
    id: int
    name: str
    produced_by: str

class Child(BaseModel):
    id: int
    name: str

    cars: List[Car] = []
    async def resolve_cars(self):
        return await get_cars_by_child(self.id)

    description: str = ''
    def post_description(self):
        desc = ', '.join([c.name for c in self.cars])
        return f'{self.name} owns {len(self.cars)} cars, they are: {desc}'

children = await Resolver.resolve([
        Child(id=1, name="Titan"),
        Child(id=1, name="Siri")]
    )

```

当定义完对象方法， 并初始化好对象后， pydantic-resolve 内部会对数据做遍历， 执行这些方法来处理数据， 最终获取所有数据。

```python
[
    Child(id=1, name="Titan", cars=[
        Car(id=1, name="Focus", produced_by="Ford")],
        description="Titan owns 1 cars, they are: Focus"
        ),
    Child(id=1, name="Siri", cars=[
        Car(id=3, name="Seal", produced_by="BYD")],
        description="Siri owns 1 cars, they are Seal")
]
```

对比面向过程的代码需要执行遍历和额外维护并发逻辑。

```python
import asyncio

async def handle_child(child):
    cars = await get_cars()
    child.cars = cars

    cars_desc = '.'.join([c.name for c in cars])
    child.description = f'{child.name} owns {len(child.cars)} cars, they are: {car_desc}'

tasks = []
for child in children:
    tasks.append(handle(child))

await asyncio.gather(*tasks)
```


搭配 DataLoader， pydantic-resolve 可以避免多层获取数据时容易发生的 N+1 查询， 优化性能。

使用 DataLoader 还可以让定义的 class 片段在任意位置被复用。

除此以外它还提供了 [expose](./api.zh.md#ancestor_context) 和 [collector](./api.zh.md#collector) 机制为跨层的数据处理提供了便利。

## 安装

```
pip install pydantic-resolve
```

从 pydantic-resolve v1.11.0 开始， 将同时兼容 pydantic v1 和 v2。
