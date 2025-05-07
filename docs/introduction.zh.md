# 简介

pydantic-resolve 是一个帮助灵活组装数据的工具，可能是最直观的工具之一，并且与 FastAPI / Litestar / Django-ninja 配合得非常好。

您可以通过添加 `resolve_field` 函数轻松扩展您的数据，无论位置如何，无论是列表还是单个数据。

> 它还支持 dataclass

```python
from pydantic import BaseModel
from pydantic_resolve import Resolver, build_list
from aiodataloader import DataLoader


# 故事和任务的 ER 模型
# ┌───────────┐
# │           │
# │   story   │
# │           │
# └─────┬─────┘
#       │
#       │   拥有多个 (TaskLoader)
#       │
#       │
# ┌─────▼─────┐
# │           │
# │   task    │
# │           │
# └───────────┘

class TaskLoader(DataLoader):
    async def batch_load_fn(self, story_ids):
        tasks = await get_tasks_by_ids(story_ids)
        return build_list(tasks, story_ids, lambda t: t.story_id)

class BaseTask(BaseModel):
    id: int
    story_id: int
    name: str

class BaseStory(BaseModel):
    id: int
    name: str

class Story(BaseStory):  # 继承和组合
    tasks: list[BaseTask] = []
    def resolve_tasks(self, loader=LoaderDepend(TaskLoader)):
        return loader.load(self.id)

stories = await get_raw_stories()
stories = [Story(**s) for s in stories)]
```

## 安装

```
pip install pydantic-resolve
```

从 pydantic-resolve v1.11.0 开始，它支持 pydantic v1 和 v2。

## 特性

### Dataloader

Dataloader 提供了一种通用的方法来关联数据，而无需担心 N+1 查询。

一旦定义了实体的查询方法和实体关联的查询方法（DataLoaders），剩下的就是在 pydantic 层面进行声明性定义。（查询细节封装在方法和 DataLoaders 中。）

### 后处理

pydantic-resolve 解决的另一个问题是将 ER 模型数据转换为视图数据的过程，您可以使用 `expose` 将祖先节点的数据暴露给后代节点，或使用 `collect` 工具将后代节点的最终数据收集到祖先节点中，从而轻松实现数据模式的重构。

这是一个简单的故事和任务的 ER 模型及其代码实现。

作为数据组合的工具，如果它仅支持挂载相关数据，那就不太花哨了，pydantic-resolve 提供了一个额外的生命周期钩子用于后处理方法。

这个后处理过程可以帮助将业务对象（在解析过程中生成）转换为视图对象。

<img width="743" alt="image" src="https://github.com/user-attachments/assets/cdcf82a7-bfd6-4b71-8221-a8f06500ebb0" />

在所有解析过程完成后，您将能够立即调整字段，并且它有许多有用的参数，甚至支持异步。

例如，计算额外字段：

```python
class Story(BaseModel):
    id: int
    name: str

    tasks: list[Task] = []
    def resolve_tasks(self, loader=LoaderDepend(TaskLoader)):
        return loader.load(self.id)

    ratio: float = 0
    def post_ratio(self):
        return len([t for t in tasks if task.done is True]) / len(self.tasks)
```

### 祖先和后代之间的通信

此示例显示了以下功能：1 将特定数据暴露给后代，2 从后代收集数据。

在解析过程中：

- 读取故事列表
- 将故事名称暴露给任务

在后处理过程中：

- 将所有任务收集到 Data.tasks 中
- 在序列化期间隐藏 Data.stories

现在 Data 仅包含每个任务的故事名称。

```python
class BaseTask(BaseModel):
    id: int
    story_id: int
    name: str

class BaseStory(BaseModel):
    id: int
    name: str

class Task(BaseTask):
    story_name: str = ''
    def resolve_story_name(self, ancestor_context):
        return ancestor_context['story_name'] # 读取直接祖先的 story_name

class Story(BaseStory):
    __pydantic_resolve_expose__ = {'name': 'story_name'}  # 将名称（作为 story_name）暴露给后代节点
    __pydantic_resolve_collect__ = {'tasks': 'task_collector'}  # 任务将由 task_collector 收集

    tasks: list[BaseTask] = []
    def resolve_tasks(self, loader=LoaderDepend(TaskLoader)):
        return loader.load(self.id)

class Data(BaseModel):
    stories: list[Story] = Field(default_factory=list, exclude=True)
    async def resolve_stories(self):
        return await get_raw_stories()

    tasks: list[Task] = []
    def post_tasks(self, collector=Collector('task_collector', flat=True)):  # flat=True 以避免列表嵌套
        return collector.values()
```

## 为什么创建它？

### 要解决的问题

数据组合的典型流程包含以下步骤：

1. 查询根数据（单个项目或项目数组）
2. 查询相关数据 a、b、c ...
3. 修改数据，从叶子数据到根数据

以故事和任务为例，我们获取任务并为每个故事分组，然后进行一些业务计算。

```python
# 1. 查询根数据
stories = await query_stories()

# 2. 查询相关数据
story_ids = [s.id for s in stories]
tasks = await get_all_tasks_by_story_ids(story_ids)

story_tasks = defaultdict(list)

for task in tasks:
    story_tasks[task.story_id].append(task)

for story in stories:
    tasks = story_tasks.get(story.id, [])

    # 3. 修改数据
    story.total_task_time = sum(task.time for task in tasks)
    story.total_done_tasks_time = sum(task.time for task in tasks if task.done)
```

在这段代码中，我们处理了任务查询、组合（按故事分组任务）和最终的业务计算。

但存在一些问题：

- 定义了临时变量，但从业务计算的角度来看，它们是无用的。
- 业务逻辑位于 `for` 缩进内。
- 组合部分很无聊。

如果我们再添加一层，例如添加冲刺，情况会变得更糟。

```python
# 1. 查询根数据
sprints = await query_sprints()

# 2-1. 查询相关数据，故事
sprint_ids = [s.id for s in sprints]
stories = await get_all_stories_by_sprint_id(sprint_ids)

# 2-2. 查询相关数据，任务
story_ids = [s.id for s in stories]
tasks = await get_all_tasks_by_story_ids(story_ids)

sprint_stories = defaultdict(list)
story_tasks = defaultdict(list)

for story in stories:
    sprint_stories[story.sprint_id].append(story)

for task in tasks:
    story_tasks[task.story_id].append(task)

for sprint in sprints:
    stories = sprint_stories.get(sprint.id, [])
    sprint.stories = stories

    for story in stories:
        tasks = story_tasks.get(story.id, [])

        # 3-1. 修改数据
        story.total_task_time = sum(task.time for task in tasks)
        story.total_done_task_time = sum(task.time for task in tasks if task.done)

    # 3-2. 修改数据
    sprint.total_time = sum(story.total_task_time for story in stories)
    sprint.total_done_time = sum(story.total_done_task_time for story in stories)
```

仅用于查询和组合数据就花费了大量代码，并且业务计算混杂在 for 循环中。

> 使用广度优先方法以最小化查询次数。

### 解决方案

如果我们可以摆脱这些查询和组合，代码可以简化，让 pydantic-resolve 处理它，甚至是 for 循环。

pydantic-resolve 可以帮助**将它们分开**，将查询和组合委托给 Dataloader，内部处理遍历。

这样我们就可以专注于**业务计算**。

```python
from pydantic_resolve import Resolver, LoaderDepend, build_list
from aiodataloader import DataLoader

# 数据获取，dataloader 将按故事分组任务。
class TaskLoader(DataLoader):
    async def batch_load_fn(self, story_ids):
        tasks = await get_all_tasks_by_story_ids(story_ids)
        return build_list(tasks, story_ids, lambda t: t.story_id)

# 核心业务逻辑
class Story(Base.Story):
    # 在 resolve_method 中使用 dataloader 获取任务
    tasks: List[Task] = []
    def resolve_tasks(self, loader=LoaderDepend(TaskLoader)):
        return loader.load(self.id)

    # 获取后计算，在 post_method 中
    total_task_time: int = 0
    def post_total_task_time(self):
        return sum(task.time for task in self.tasks)

    total_done_task_time: int = 0
    def post_total_done_task_time(self):
        return sum(task.time for task in self.tasks if task.done)

# 遍历并执行方法（runner）
# 查询根数据
stories: List[Story] = await query_stories()
await Resolver().resolve(stories)
```

对于第二种情况：

```python
# 数据获取
class TaskLoader(DataLoader):
    async def batch_load_fn(self, story_ids):
        tasks = await get_all_tasks_by_story_ids(story_ids)
        return build_list(tasks, story_ids, lambda t: t.story_id)

class StoryLoader(DataLoader):
    async def batch_load_fn(self, sprint_ids):
        stories = await get_all_stories_by_sprint_ids(sprint_ids)
        return build_list(stories, sprint_ids, lambda t: t.sprint_id)

# 核心业务逻辑
class Story(Base.Story):
    tasks: List[Task] = []
    def resolve_tasks(self, loader=LoaderDepend(TaskLoader)):
        return loader.load(self.id)

    total_task_time: int = 0
    def post_total_task_time(self):
        return sum(task.time for task in self.tasks)

    total_done_task_time: int = 0
    def post_total_done_task_time(self):
        return sum(task.time for task in self.tasks if task.done)

class Sprint(Base.Sprint):
    stories: List[Story] = []
    def resolve_stories(self, loader=LoaderDepend(StoryLoader)):
        return loader.load(self.id)

    total_time: int = 0
    def post_total_time(self):
        return sum(story.total_task_time for story in self.stories)

    total_done_time: int = 0
    def post_total_done_time(self):
        return sum(story.total_done_task_time for story in self.stories)


# 遍历并执行方法（runner）
# 查询根数据
sprints: List[Sprint] = await query_sprints()
await Resolver().resolve(sprints)
```

不再有缩进，不再有临时辅助变量，不再有 for 循环（和缩进）。

所有关系和遍历都由 pydantic/dataclass 类定义。

> 为什么不使用 ORM 关系进行查询和组合？
>
> Dataloader 是不同实现的通用接口
> 如果 ORM 提供了相关数据，我们只需要简单地删除 resolve_method 和 dataloader。

## 它是如何工作的？

它可以在数据组合过程中减少代码复杂性，使代码接近 ER 模型，从而更易于维护。

> 使用面向 ER 的建模方法，它可以使我们的开发效率提高 3 到 5 倍，并减少 50% 以上的代码。

在 pydantic 的帮助下，它可以像 GraphQL 一样描述图状关系的数据结构，并且在获取数据时可以根据业务需求进行调整。

它可以轻松地与 FastAPI 一起运行，在后端构建前端友好的数据结构，并以 TypeScript SDK 的形式提供给前端。

基本上它只是为 pydantic 和 dataclass 对象提供了解析和后处理方法。

- 解析用于获取数据
- 后处理用于在获取数据后进行额外处理

这是一个递归过程，解析过程在所有后代完成后结束。

![](./images/life-cycle.png)

以 Sprint、Story 和 Task 为例：

![](./images/real-sample.png)

当对象方法定义并初始化对象时，pydantic-resolve 将在内部遍历数据，执行这些方法以处理数据，最终获取所有数据。

借助 DataLoader，pydantic-resolve 可以避免在多层获取数据时容易出现的 N+1 查询问题，优化性能。

使用 DataLoader 还允许定义的类片段在任何位置重用。

此外，它还提供了暴露和收集机制，以方便跨层数据处理。

## Hello world 示例

最初我们有一本书的列表，然后我们想要附加作者信息。

```python
import asyncio
from pydantic_resolve import Resolver

# 数据
books = [
    {"title": "1984", "year": 1949},
    {"title": "To Kill a Mockingbird", "year": 1960},
    {"title": "The Great Gatsby", "year": 1925}]

persons = [
    {"name": "George Orwell", "age": 46},
    {"name": "Harper Lee", "age": 89},
    {"name": "F. Scott Fitzgerald", "age": 44}]

book_author_mapping = {
    "1984": "George Orwell",
    "To Kill a Mockingbird": "Harper Lee",
    "The Great Gatsby": "F. Scott Fitzgerald"}

async def get_author(title: str) -> Person:
    await asyncio.sleep(0.1)
    author_name = book_author_mapping[title]
    if not author_name:
        return None
    author = [person for person in persons if person['name'] == author_name][0]
    return Person(**author)

class Person(BaseModel):
    name: str
    age: int


class Book(BaseModel):
    title: str
    year: int
    author: Optional[Person] = None

    async def resolve_author(self):
        return await get_author(self.title)

books = [Book(**book) for book in books]
books_with_author = await Resolver().resolve(books)

```

输出

```python
[
    Book(title='1984', year=1949, author=Person(name='George Orwell', age=46)),
    Book(title='To Kill a Mockingbird', year=1960, author=Person(name='Harper Lee', age=89)),
    Book(title='The Great Gatsby', year=1925, author=Person(name='F. Scott Fitzgerald', age=44))
]
```

在内部，它并发执行异步函数，看起来像这样：

```python
import asyncio

async def handle_author(book: Book):
    author = await get_author(book.title)
    book.author = author

await asyncio.gather(*[handle_author(book) for book in books])
```

## 文档

- **文档**: https://allmonday.github.io/pydantic-resolve/v2/introduction/
- **演示**: https://github.com/allmonday/pydantic-resolve-demo
- **面向组合的模式**: https://github.com/allmonday/composition-oriented-development-pattern

## 测试和覆盖率

```shell
tox
```

```shell
tox -e coverage
python -m http.server
```

最新覆盖率：97%

## 听取您的意见

[Discord](https://discord.com/channels/1197929379951558797/1197929379951558800)
