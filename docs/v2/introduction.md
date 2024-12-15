# Introduction

pydantic-resolve is a lightweight wrapper library based on pydantic. It adds resolve and post methods to pydantic and dataclass objects.

If you have ever written similar code and felt unsatisfied, pydantic-resolve can come in handy.

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

this snippet mixed traversal, temp variables, data fetching and business logic together.

pydantic-resolve can help **split them apart**, let you focus on the core business logic.


```python
from pydantic_resolve import Resolver, LoaderDepend, build_list
from aiodataloader import DataLoader


# data fetching
class TaskLoader(DataLoader):
    async def batch_load_fn(self, story_ids):
        tasks = await get_all_tasks_by_story_ids(story_ids)
        return build_list(tasks, story_ids, lambda t: t.story_id)

# core business logics
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
  
# traversal and execute methods (runner)
await Resolver().resolve(stories)
```

pydantic-resolve can easily be applied to more complicated scenarios, such as:

A list of sprint, each sprint owns a list of story, each story owns a list of task, and do some modifications or calculations.

```python
# data fetching
class TaskLoader(DataLoader):
    async def batch_load_fn(self, story_ids):
        tasks = await get_all_tasks_by_story_ids(story_ids)
        return build_list(tasks, story_ids, lambda t: t.story_id)

class StoryLoader(DataLoader):
    async def batch_load_fn(self, sprint_ids):
        stories = await get_all_stories_by_sprint_ids(sprint_ids)
        return build_list(stories, sprint_ids, lambda t: t.sprint_id)

# core business logic
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
    

# traversal and execute methods (runner)
await Resolver().resolve(sprints)
```

It can reduce the code complexity in the data assembly process, making the code closer to the ER model and more maintainable.

With the help of pydantic, it can describe data structures in a graph-like relationship like GraphQL, and can also make adjustments based on business needs while fetching data.

It can easily cooperate with FastAPI to build frontend friendly data structures on the backend and provide them to the frontend in the form of a TypeScript SDK.

> Using an ERD-oriented modeling approach, it can provide you with a 3 to 5 times increase in development efficiency and reduce code volume by more than 50%.

It provides resolve and post methods for pydantic objects.

- resolve is usually used to fetch data
- post can be used to do additional processing after fetching data


When the object methods are defined and the objects are initialized, pydantic-resolve will internally traverse the data, execute these methods to process the data, and finally obtain all the data.

With DataLoader, pydantic-resolve can avoid the N+1 query problem that easily occurs when fetching data in multiple layers, optimizing performance.

Using DataLoader also allows the defined class fragments to be reused in any location.

In addition, it also provides expose and collector mechanisms to facilitate cross-layer data processing.

## Installation

```
pip install pydantic-resolve
```

Starting from pydantic-resolve v1.11.0, it will be compatible with both pydantic v1 and v2.
