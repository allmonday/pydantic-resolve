[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![PyPI Downloads](https://static.pepy.tech/badge/pydantic-resolve/month)](https://pepy.tech/projects/pydantic-resolve)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)


Pydantic-resolve is a Pydantic based approach to construct complex data declaratively and progressively, without writing any imperative glue code.

Its best use case is building complex API data, especially in UI integration scenarios, it can be used as a replacement for GraphQL, reusing most of the code while offering better performance and maintainability.

It introduces resolve methods for on-demand data fetching, and post methods for post process requirements.

It also provides the capability for cross-layer node data transmission.

Starting from pydantic-resolve v2, `ErDiagram` is supported, we can use it to declare application level `Entity Relationship` to better maintain the core business models.

With the support of ERD, the constructed data will have better maintainability, being easy to write and read.

It could be seamlessly integrated with modern Python web frameworks including FastAPI, Litestar, and Django-ninja.

For FastAPI developers, we can visualize the dependencies of schemas by installing [fastapi-voyager](https://github.com/allmonday/fastapi-voyager), visit [live demo](https://www.newsyeah.fun/voyager/?tag=sample_1)


## Installation

```
# latest v1
pip install pydantic-resolve==1.13.5

# v2
pip install pydantic-resolve
```

Starting from pydantic-resolve v1.11.0, both pydantic v1 and v2 are supported.

Starting from pydantic-resolve v2.0.0, it only supports pydantic v2, pydantic v1 and dataclass are dropped, anything else are backward compatible.

## Basic Usage

In this part, we will introduce some fundamental features that allow us to freely combine data just like a GraphQL query.

### Pick fields from source class

`DefineSubset` can pick wanted fields and generate a new pydantic class.


```python
from pdyantic_resolve import DefineSubset
import app.team.schema as team_schema

class Team(DefineSubset)
    __subset__ = (team_schema.Team, ('id', 'name'))

@route.get('/teams', response_model=List[Team])
async def get_teams(session: AsyncSession = Depends(db.get_session)):
    teams = await tmq.get_teams(session)
    return teams
```

### Attach related data

use `resolve_{field}` method and dataloader to efficiently fetch associated data

Inside the dataloader is a simple batch-by-ids query.

Of course, you can continue to take subsets of the associated data.

```python
from pydantic_resolve import Loader, Resolver
import app.team.schema as team_schema
import app.sprint.schema as sprint_schema
import app.sprint.loader as sprint_loader
import app.user.schema as user_schema
import app.user.loader as user_loader

class Sprint(DefineSubset):
    __subset__ = (sprint_schema.Sprint, ('id', 'name'))

class Team(DefineSubset)
    __subset__ = (team_schema.Team, ('id', 'name'))

    sprints: list[Sprint] = []
    def resolve_sprints(self, loader=Loader(sprint_loader.team_to_sprint_loader)):
        return loader.load(self.id)
    
    members: list[user_schema.User] = []
    def resolve_members(self, loader=Loader(user_loader.team_to_user_loader)):
        return loader.load(self.id)

@route.get('/teams', response_model=List[Team])
async def get_teams(session: AsyncSession = Depends(db.get_session)):
    teams = await tmq.get_teams(session)

    teams = [Team.model_validate(t) for t in teams] # <---
    teams = await Resolver().resolve(teams)         # <---

    return teams
```


## Advanced Usage

Here, we will introduce the advanced features of pydantic resolve, which can help resolve various issues during the data construction process（which are very difficult in scope of GraphQL).

They are ErDiagram, `post_{field}` methods, ExposeAs and SendTo.

Here is the [live demo](https://www.newsyeah.fun/voyager/?tag=demo) and [source code](https://github.com/allmonday/composition-oriented-development-pattern/tree/master/src/services)

### 1. Define schema (entity) and their relationships

> for classes defined later, We can use string form to express.

```python
from pydantic_resolve import base_entity, Relationship

BaseEntity = base_entity()

class Sprint(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship( field='id', target_kls=list['Story'], loader=story_loader.sprint_to_story_loader)
    ]

    id: int
    name: str
    status: str
    team_id: int

    model_config = ConfigDict(from_attributes=True)

class Story(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship( field='id', target_kls=list['Task'], loader=task_loader.story_to_task_loader),
        Relationship( field='owner_id', target_kls='User', loader=user_loader.user_batch_loader)
    ]

    id: int
    name: str
    owner_id: int
    sprint_id: int

    model_config = ConfigDict(from_attributes=True)

class Task(BaseModel):
    id: int
    name: str
    owner_id: int
    story_id: int
    estimate: int

    model_config = ConfigDict(from_attributes=True)

class User(BaseModel):
    id: int
    name: str
    level: str

    model_config = ConfigDict(from_attributes=True)

diagram = BaseEntity.get_diagram()
config_global_resolver(diagram)  # register into Resolver
```

The dataloader is defined for general usage, if other approach such as ORM relationship is available, it can be easily replaced.
DataLoader's implementation supports all kinds of data sources, from database queries to microservice RPC calls.

Here we use SqlAlchemy.

```python
from .model import Task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import src.db as db
from pydantic_resolve import build_list

# --------- user_id -> user ----------
async def batch_get_users_by_ids(session: AsyncSession, user_ids: list[int]):
    users = (await session.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
    return users

async def user_batch_loader(user_ids: list[int]):
    async with db.async_session() as session:
        users = await batch_get_users_by_ids(session, user_ids)
        return build_object(users, user_ids, lambda u: u.id)

# ---------- task id -> task ------------
async def batch_get_tasks_by_ids(session: AsyncSession, story_ids: list[int]):
    users = (await session.execute(select(Task).where(Task.story_id.in_(story_ids)))).scalars().all()
    return users

async def story_to_task_loader(story_ids: list[int]):
    async with db.async_session() as session:
        tasks = await batch_get_tasks_by_ids(session, story_ids)
        return build_list(tasks, story_ids, lambda u: u.story_id)
```

ErDiagram can also be declared seperately.

```python
diagram = ErDiagram(
    configs=[
        ErConfig(
            kls=Story,
            relationships=[
                Relationship( field='id', target_kls=list[Task], loader=task_loader.story_to_task_loader),
                Relationship( field='owner_id', target_kls=User, loader=user_loader.user_batch_loader)
            ]
        ),
        ErConfig(
            kls=Task,
            relationships=[
                Relationship( field='owner_id', target_kls=User, loader=user_loader.user_batch_loader)
            ]
        )
    ]
)

config_global_resolver(diagram)  # register into Resolver
```

<img width="758" height="444" alt="image" src="https://github.com/user-attachments/assets/58d95751-2871-40e2-a69a-8a52a2872621" />


### 2. Attach related business data.

As we introduced in `basic usage` section, we can simpliy inherit or use `DefineSubset` to reuse Entity fields and extends new field and resolve them by dataloaders.

[view in voyager](https://www.newsyeah.fun/voyager/?tag=demo&route=src.router.demo.router.get_stories_with_detail)

As ErDiagram is provided, we don't need to write resolve methods, just provide the foreign key name in `LoadBy`, those methods will be `compiled` in analytic phase before execution.

```python
from pydantic_resolve import LoadBy

class Task(BaseTask):
    user: Annotated[Optional[BaseUser], LoadBy('owner_id')] = None

class Story(DefineSubset):
    __subset__ = (BaseStory, ('id', 'name', 'owner_id'))

    tasks: Annotated[list[Task], LoadBy('id')] = []
    assignee: Annotated[Optional[BaseUser], LoadBy('owner_id')] = None        
```

### 3. Adjust data for UI details

The data you build in previous stage often is not directly ready for UI display. Many details require a second pass over the composed data, for example:

- Task names need a prefix from their parent Story name
- A Story needs the total estimate of all its Tasks
- A Story needs to collect all developers involved across its Tasks

In Pydantic Resolve, these can be done with `post_*` methods immediately, without an extra traversal.

From a lifecycle perspective, a Pydantic model's `post_*` methods run only after all `resolve_*` methods have finished. So from a `post_*` method, all resolved data is already ready.

In other words, `post_*` is a hook provided during traversal, and you can use it to perform all kinds of operations after data fetching.

Let's explain using the three cases above.

#### 1: A node exposes its fields to all descendants

> Task names need a prefix from their parent Story name

[view in voyager](https://www.newsyeah.fun/voyager/?tag=demo&route=src.router.demo.router.get_stories_with_detail_3), double click `Story3`

By defining `__pydantic_resolve_expose__`, you can expose the current model's field data to descendant nodes.

`__pydantic_resolve_expose__ = { 'name': 'story_name' }`

Note: the key (`name`) is the field name, and the value (`story_name`) is an alias used by descendants to look up the value. This alias must be “globally” unique within the whole tree rooted at `Story`.

Descendants can read the value via `ancestor_context['story_name']`.

[source code](https://github.com/allmonday/composition-oriented-development-pattern/blob/master/src/router/demo/schema3.py)

```python

# post case 1
class Task3(BaseTask):
	user: Annotated[Optional[BaseUser], LoadBy('owner_id')] = None

	fullname: str = ''
	def post_fullname(self, ancestor_context):  # Access story.name from parent context
		return f'{ancestor_context["story_name"]} - {self.name}'

class Story3(DefineSubset):
	__subset__ = (BaseStory, ('id', 'name', 'owner_id'))
	__pydantic_resolve_expose__ = {'name': 'story_name'}

	tasks: Annotated[list[Task3], LoadBy('id')] = []
	assignee: Annotated[Optional[BaseUser], LoadBy('owner_id')] = None
```

Here is another way to define expose, `SubsetConfig` provides expose_as configuration.

```python
from pydantic_resolve import SubsetConfig

class Story3(DefineSubset):
	__subset__ = SubsetConfig(
        kls=BaseStory, 
        fields=['id', 'name', 'owner_id'],
        expose_as=[('name', 'story_name')])

	tasks: Annotated[list[Task3], LoadBy('id')] = []
	assignee: Annotated[Optional[BaseUser], LoadBy('owner_id')] = None
```

or use `ExposeAs` for normal scenarios

```python
from pydantic_resolve import ExposeAs

class Story3(BaseModel):
    id: int
    name: Annotated[str, ExposeAs('story_name')]  # <---
    owner_id: int
    sprint_id: int

	tasks: Annotated[list[Task3], LoadBy('id')] = []
	assignee: Annotated[Optional[BaseUser], LoadBy('owner_id')] = None

    model_config = ConfigDict(from_attributes=True)
```

> Note that fields processed by resolve/post cannot use `expose as` because the data is not yet ready.

#### 2: Compute extra fields from resolved data

> How to compute the total estimate of all tasks in each story?

[view in voyager](https://www.newsyeah.fun/voyager/?tag=demo&route=src.router.demo.router.get_stories_with_detail_2), double click `Story2`

Because `post_*` runs after `resolve_*`, this is straightforward—just `sum` it.

```python
class Task2(BaseTask):
	user: Annotated[Optional[BaseUser], LoadBy('owner_id')] = None

class Story2(DefineSubset):
	__pydantic_resolve_subset__ = (BaseStory, ('id', 'name', 'owner_id'))

	tasks: Annotated[list[Task2], LoadBy('id')] = []
	assignee: Annotated[Optional[BaseUser], LoadBy('owner_id')] = None

	total_estimate: int = 0
	def post_total_estimate(self):
		return sum(task.estimate for task in self.tasks)
```

#### 3: An ancestor collects data from descendants

> A story needs to collect all developers involved across its tasks

[view in voyager](https://www.newsyeah.fun/voyager/?tag=demo&route=src.router.demo.router.get_stories_with_detail_1), double click `Task1`, and view `source code`

To implement collection, define a `Collector` in an ancestor node. Similar to `expose`, all descendants can send data to that `Collector`.

Then read the results via `collector.values()`.

Unlike `expose`, the alias inside a `Collector` does not need to be “globally” unique. Collectors with the same alias are scoped by the ancestor/descendant relationship.

In descendant nodes, `__pydantic_resolve_collect__ = {'user': 'related_users'}` declares that it will send `user` to the ancestor collector named `related_users`.

`__pydantic_resolve_collect__` supports many forms:

```
# send user to related_users
__pydantic_resolve_collect__ = {'user': 'related_users'}

# send user, id to related users
__pydantic_resolve_collect__ = {('id', 'user'): 'related_users'}

#  send user, id to related_users and all_users
__pydantic_resolve_collect__ = {('id', 'user'): ('related_users', 'all_users')}
```

The default `Collector` provided by Pydantic Resolve collects values into a list. You can also implement `ICollector` to build custom collectors for your own subset needs.

For more details, view this [page](./expose_and_collect.md#_2)

Here is the complete code. `related_users` will collect all `user` values. (Note: this example does not deduplicate.)

```python
class Task1(BaseTask):
	__pydantic_resolve_collect__ = {'user': 'related_users'}  # Propagate user to collector: 'related_users'

	user: Annotated[Optional[BaseUser], LoadBy('owner_id')] = None

class Story1(DefineSubset):
	__pydantic_resolve_subset__ = (BaseStory, ('id', 'name', 'owner_id'))

	tasks: Annotated[list[Task1], LoadBy('id')] = []
	assignee: Annotated[Optional[BaseUser], LoadBy('owner_id')] = None

	related_users: list[BaseUser] = []
	def post_related_users(self, collector=Collector(alias='related_users')):
		return collector.values()
```

Here is another option, use `SendTo`

```python
from pydantic_resolve import SendTo

class Task1(BaseTask):
	user: Annotated[Optional[BaseUser], LoadBy('owner_id'), SendTo('related_users')] = None
```

### 4. Execute

Pydantic Resolve provides `Resolver().resolve(data)` as the entry point.

First, provide data of type `Story`. Then `Resolver` will execute your configured logic to fetch and transform data.

```python
from pydantic_resolve import Resolver

stories = [Story(**s) for s in await query_stories()]
data = await Resolver().resolve(stories)
```

## How it works

The process is similar to breadth-first traversal, with additional hooks after the traversal of descendant nodes is completed.

Compared with GraphQL, both traverse descendant nodes recursively and support resolver functions and DataLoaders. The key difference is post-processing: from the post-processing perspective, resolved data is always ready for further transformation, regardless of whether it came from resolvers or initial input.

![](./docs/images/lifecycle.jpeg)

pydantic class can be initialized by deep nested data (which means descendant are provided in advance), then just need to run the post process.

![](./docs/images/preload.png)

Within post hooks, developers can read descendant data, adjust existing fields, compute derived fields.

Post hooks also enable bidirectional data flow: they can read from ancestor nodes and push values up to ancestors, which is useful for adapting data to varied business requirements.

![](./docs/images/communication.jpeg)


## Documentation

- **Documentation**: https://allmonday.github.io/pydantic-resolve/
- **Composition-Oriented Pattern**: https://github.com/allmonday/composition-oriented-development-pattern
- **Live demo**: https://www.newsyeah.fun/voyager/?tag=sample_1
- [Resolver Pattern: A Better Alternative to GraphQL in BFF (api-integration).](https://github.com/allmonday/resolver-vs-graphql/blob/master/README-en.md)


## Performance tips

For projects using FastAPI + SQLAlchemy, you need to pay attention to the lifecycle of the session generated by `Depends(async_session)`.

When the number of concurrent requests is greater than or equal to the session pool size, a deadlock situation may occur. This is because the session provided by `Depends` waits until the end of the request to be released, while the dataloader in `Resolver` requests a new session, leading to a situation where new sessions cannot be acquired and existing ones cannot be released.

The solution is to avoid long-term occupation of the `Depends` session and release it immediately after obtaining the required data. This also aligns with best practices: the lifecycle of a database session should be as short as possible.

In terms of code examples, this means adding `session.close()`, or simply avoiding the use of sessions generated by `Depends` and using a context manager to control the session lifecycle directly.

```python
@router.get("/team/{team_id}/stories-with-mr", response_model=List[story_schema.StoryWithMr])
async def stories_with_mr_get(
        team_id: int,
        sprint_id: Optional[int] = None,
        session: AsyncSession = Depends(get_async_session)):

    rows = await sq.get_stories(team_id=team_id, sprint_id=sprint_id, session=session)

    # release session immediately after use
    await session.close()  

    items = [story_schema.StoryWithMr.model_validate(r) for r in rows]
    items = await Resolver().resolve(items)  # dataloader will create new session internally
    return items
```


## Development

```shell
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

uv run pytest tests/
```

## Testing and Coverage

```shell
tox
```

```shell
tox -e coverage
python -m http.server
```

Current test coverage: 97%
