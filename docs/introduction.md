pydantic-resolve is a general-purpose data composition tool that supports multi-level data fetching, node-level post-processing, and cross-node data transmission.

It organizes and manages data in a declarative way, greatly improving code readability and maintainability.

In the example, you inherit BaseStory and BaseTask to reuse and extend required fields, add tasks to BaseStory, and add a user field to each task.

```python
from pydantic_resolve import Resolver
from biz_models import BaseTask, BaseStory, BaseUser
from biz_services import UserLoader, StoryTaskLoader

class Task(BaseTask):
    user: Optional[BaseUser] = None
    def resolve_user(self, loader=Loader(UserLoader)):
        return loader.load(self.assignee_id) if self.assignee_id else None

class Story(BaseStory):
    tasks: list[Task] = []
    def resolve_tasks(self, loader=Loader(StoryTaskLoader)):
        # this loader returns BaseTask,
        # Task inherits from BaseTask so it can be initialized from it, then fetch the user.
        return loader.load(self.id)

stories = [Story(**s) for s in await query_stories()]
data = await Resolver().resolve(stories)
```

Given initial BaseStory data:

```json
[
  { "id": 1, "name": "story - 1" },
  { "id": 2, "name": "story - 2" }
]
```

pydantic-resolve can expand it into the complex structure you declare:

```json
[
  {
    "id": 1,
    "name": "story - 1",
    "tasks": [
      {
        "id": 1,
        "name": "design",
        "user": {
          "id": 1,
          "name": "tangkikodo"
        }
      }
    ]
  },
  {
    "id": 2,
    "name": "story - 2",
    "tasks": [
      {
        "id": 2,
        "name": "add ut",
        "user": {
          "id": 2,
          "name": "john"
        }
      }
    ]
  }
]
```

If you have GraphQL experience, this article provides a comprehensive discussion and comparison: [Resolver Pattern: A Better Alternative to GraphQL in BFF](https://github.com/allmonday/resolver-vs-graphql/blob/master/README-en.md)

Unlike ORM or GraphQL data fetching solutions, pydantic-resolve's post-processing capability provides a powerful solution for building business data, avoiding repetitive loops and temporary variables in business code, simplifying logic, and improving maintainability.

## Installation

```
pip install pydantic-resolve
```

From v1.11.0, pydantic-resolve supports both pydantic v1 and v2.

## Documentation

- **Docs**: [https://allmonday.github.io/pydantic-resolve/v2/introduction/](https://allmonday.github.io/pydantic-resolve/v2/introduction/)
- **Demo repository**: [https://github.com/allmonday/pydantic-resolve-demo](https://github.com/allmonday/pydantic-resolve-demo)
- **Composition-oriented development pattern**: [https://github.com/allmonday/composition-oriented-development-pattern](https://github.com/allmonday/composition-oriented-development-pattern)

## Three Steps to Build Complex Data

Using Story and Task from Agile as an example:

### 1. Define Domain Models

Establish entity relationships as the base data model (for persistence layer; these relationships are stable and rarely change).

<img width="630px" alt="image" src="https://github.com/user-attachments/assets/2656f72e-1af5-467a-96f9-cab95760b720" />

```python
from pydantic import BaseModel

class BaseStory(BaseModel):
    id: int
    name: str
    assignee_id: Optional[int]
    report_to: Optional[int]

class BaseTask(BaseModel):
    id: int
    story_id: int
    name: str
    estimate: int
    done: bool
    assignee_id: Optional[int]

class BaseUser(BaseModel):
    id: int
    name: str
    title: str
```

```python
from aiodataloader import DataLoader
from pydantic_resolve import build_list, build_object

class StoryTaskLoader(DataLoader):
    async def batch_load_fn(self, keys: list[int]):
        tasks = await get_tasks_by_story_ids(keys)
        return build_list(tasks, keys, lambda x: x.story_id)

class UserLoader(DataLoader):
    async def batch_load_fn(self, keys: list[int]):
        users = await get_tuser_by_ids(keys)
        return build_object(users, keys, lambda x: x.id)
```

DataLoader implementations support various data sources, from database queries to microservice RPC calls.

### 2. Compose Models for Business Needs

For example, you may need to build Story (with tasks, assignee, reporter), Task (with user) business models.

You can inherit base models and extend fields as needed. This composition is flexible and can be dynamically modified, but dependencies are constrained by the previous definitions.

You can treat it as a subset of the ER model.

<img width="709" alt="image" src="https://github.com/user-attachments/assets/ffc74e60-0670-475c-85ab-cb0d03460813" />

```python
from pydantic_resolve import LoaderDepend

class Task(BaseTask):
    user: Optional[BaseUser] = None
    def resolve_user(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.assignee_id) if self.assignee_id else None

class Story(BaseStory):
    tasks: list[Task] = []
    def resolve_tasks(self, loader=LoaderDepend(StoryTaskLoader)):
        return loader.load(self.id)

    assignee: Optional[BaseUser] = None
    def resolve_assignee(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.assignee_id) if self.assignee_id else None

    reporter: Optional[BaseUser] = None
    def resolve_reporter(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.report_to) if self.report_to else None
```

Use the `ensure_subset` decorator for field validation and consistency enforcement:

```python
@ensure_subset(BaseStory)
class Story(BaseModel):
    id: int
    assignee_id: int
    report_to: int

    tasks: list[BaseTask] = []
    def resolve_tasks(self, loader=LoaderDepend(StoryTaskLoader)):
        return loader.load(self.id)
```

> Once the stability and necessity of the business model are validated, you can later replace DataLoader with specialized queries for performance, such as ORM relationships with joins.

### 3. Implement View Layer Transformation

In real business scenarios, data from the persistence layer often needs extra computed fields, such as totals or filters.

pydantic-resolve's post-processing capability is ideal for these scenarios.

The `post_field` method allows data to be passed across nodes and modified after fetching.

#### Pattern 1: Collect Objects Across Layers

<img width="630px" alt="image" src="https://github.com/user-attachments/assets/2e3b1345-9e5e-489b-a81d-dc220b9d6334" />

Use `__pydantic_resolve_collect__` to send fields from the current object up to ancestor nodes that declare a collector.

```python
from pydantic_resolve import LoaderDepend, Collector

class Task(BaseTask):
    __pydantic_resolve_collect__ = {'user': 'related_users'}  # send user to 'related_users' collector

    user: Optional[BaseUser] = None
    def resolve_user(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.assignee_id)

class Story(BaseStory):
    tasks: list[Task] = []
    def resolve_tasks(self, loader=LoaderDepend(StoryTaskLoader)):
        return loader.load(self.id)

    assignee: Optional[BaseUser] = None
    def resolve_assignee(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.assignee_id)

    reporter: Optional[BaseUser] = None
    def resolve_reporter(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.report_to)

    # ---------- Post-processing ------------
    related_users: list[BaseUser] = []
    def post_related_users(self, collector=Collector(alias='related_users')):
        return collector.values()
```

#### Pattern 2: Compute New Fields

<img width="687" alt="image" src="https://github.com/user-attachments/assets/fd5897d6-1c6a-49ec-aab0-495070054b83" />

The post method is triggered after all resolve and post methods of the current and descendant nodes are executed, so all fields are ready for post-processing, such as calculating the total estimate of all tasks.

```python
class Story(BaseStory):
    tasks: list[Task] = []
    def resolve_tasks(self, loader=LoaderDepend(StoryTaskLoader)):
        return loader.load(self.id)

    assignee: Optional[BaseUser] = None
    def resolve_assignee(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.assignee_id)

    reporter: Optional[BaseUser] = None
    def resolve_reporter(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.report_to)

    # ---------- Post-processing ------------
    total_estimate: int = 0
    def post_total_estimate(self):
        return sum(task.estimate for task in self.tasks)
```

### Pattern 3: Access Ancestor Node Data

Use `__pydantic_resolve_expose__` to expose fields from the current object to all descendants, which can access them via `ancestor_context['alias_name']`.

```python
from pydantic_resolve import LoaderDepend

class Task(BaseTask):
    user: Optional[BaseUser] = None
    def resolve_user(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.assignee_id)

    # ---------- Post-processing ------------
    def post_name(self, ancestor_context):  # access story.name from parent context
        return f'{ancestor_context['story_name']} - {self.name}'

class Story(BaseStory):
    __pydantic_resolve_expose__ = {'name': 'story_name'}

    tasks: list[Task] = []
    def resolve_tasks(self, loader=LoaderDepend(StoryTaskLoader)):
        return loader.load(self.id)

    assignee: Optional[BaseUser] = None
    def resolve_assignee(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.assignee_id)

    reporter: Optional[BaseUser] = None
    def resolve_reporter(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.report_to)
```

### 4. Run the Resolver

```python
from pydantic_resolve import Resolver

stories: [Story(**s) for s in await query_stories()]
data = await Resolver().resolve(stories)
```

The `query_stories()` method returns an array of BaseStory data, which can be converted to Story objects. Then, use a Resolver instance to automatically transform and obtain complete descendant nodes and post-processed data.

## Technical Architecture

pydantic-resolve maintains consistency with the entity relationship model, reducing data composition complexity and enhancing maintainability. Using ER-based modeling can improve development efficiency by 3-5x and reduce code by over 50%.

pydantic-resolve provides `resolve` and `post` method hooks for pydantic and dataclass objects:

- `resolve`: handles data fetching
- `post`: performs post-processing transformations

It implements a recursive parsing process, where each node executes all resolve, post, and post_default_handler methods once. After this process, the parent node's resolve method finishes.

![](images/life-cycle.png)

For example, in a Sprint, Story, and Task hierarchy:

Sprint's resolve_stories is executed first, then Story's resolve_tasks, Task as a leaf node finishes, then Story's post_task_time and post_done_task are executed, and Story's traversal ends. Next, Sprint's post_task_time and post_total_done_task_time are triggered.

When the post method is triggered, all related descendant nodes are already processed, so refactoring resolve methods does not affect post logic (e.g., removing resolve methods and providing related data directly at the parent node, such as ORM relationships or fetching complete tree data from NoSQL).

This achieves complete decoupling of resolve and post responsibilities. For example, when handling data from GraphQL, since related data is ready, you can skip resolve methods and use post methods for various post-processing needs.

![](images/real-sample.png)

> DataLoader eliminates the N+1 query problem common in multi-level data fetching.