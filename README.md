[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![PyPI Downloads](https://static.pepy.tech/badge/pydantic-resolve/month)](https://pepy.tech/projects/pydantic-resolve)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)

<img width="1345" height="476" alt="image" src="https://github.com/user-attachments/assets/b7ce9742-40a4-4a61-97a0-61ed53076099" />


Pydantic-resolve is a Pydantic based approach to construct complex data declaratively and progressively, without writing any imperative glue code. 

Its best use case is building complex API data, in UI integration scenarios, it can be used as a replacement for GraphQL, reusing most of the code while offering better performance and maintainability.

It introduces resolve hooks for on-demand data fetching, and post hooks for normalization, transformation, and reorganization to meet diverse requirements.

Starting from pydantic-resolve v2, `ErDiagram` feautre is introduced, we can declare application level `Entity Relationship` and their default dataloader, and loaders will be applied automatically.

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

## Construct data progressively with resolve

### Day 1

I want to return list of team with fields of id and name only:

```python
from pdyantic_resolve import DefineSubset
import app.team.schema as team_schema

class Team(DefineSubset)
    __subset__ = (team_schema.Team, ('id', 'name'))

@route.get('/teams', response_model=List[Team])
async def get_teams(session: AsyncSession = Depends(db.get_session)):
    teams = await tmq.get_teams(session)
    teams = [Team.model_validate(t) for t in teams]
    return teams
```

### Day 2

I want to have sprints and members for each team additionally.

```python
from pydantic_resolve import Loader, Resolver
import app.team.schema as team_schema
import app.sprint.schema as sprint_schema
import app.sprint.loader as sprint_loader
import app.user.schema as user_schema
import app.user.loader as user_loader

class Team(DefineSubset)
    __subset__ = (team_schema.Team, ('id', 'name'))

    sprints: list[sprint_schema.Sprint] = []
    def resolve_sprints(self, loader=Loader(sprint_loader.team_to_sprint_loader)):
        return loader.load(self.id)
    
    members: list[user_schema.User] = []
    def resolve_members(self, loader=Loader(user_loader.team_to_user_loader)):
        return loader.load(self.id)

@route.get('/teams', response_model=List[Team])
async def get_teams(session: AsyncSession = Depends(db.get_session)):
    teams = await tmq.get_teams(session)
    teams = [Team.model_validate(t) for t in teams]

    teams = await Resolver().resolve(teams)

    return teams
```

### Day 3

pydantic-resolve provided a powerful feature to define application level ER diagram, it's based on Entity and Relationships.

Inside Relationship we can describe many things like load, load_many, multiple relationship or primitive loader.

```python
from pydantic_resolve import base_entity
BaseEntity = base_entity()
```

```python
from pydantic import BaseModel, ConfigDict
from pydantic_resolve import Relationship
import src.services.sprint.schema as sprint_schema
import src.services.sprint.loader as sprint_loader
import src.services.user.schema as user_schema
import src.services.user.loader as user_loader

from src.services.er_diagram import BaseEntity

class Team(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship( field='id', target_kls=list[sprint_schema.Sprint], loader=sprint_loader.team_to_sprint_loader),
        Relationship( field='id', target_kls=list[user_schema.User], loader=user_loader.team_to_user_loader)
    ]
    
    id: int
    name: str
    
    model_config = ConfigDict(from_attributes=True)
```

Then the code above can be simplified, the required dataloader will be automatically inferred.

```python
from src.services.er_diagram import BaseEntity
from pydantic_resolve import config_global_resolver

# register the diagram
diagram = BaseEntity.get_diagram()
config_global_resolver(diagram)


class Team(DefineSubset)
    __subset__ = (team_schema.Team, ('id', 'name'))

    sprints: Annotated[list[sprint_schema.Sprint], LoadBy('id')] = []
    members: Annotated[list[user_schema.User], LoadBy('id')] = []

@route.get('/teams', response_model=List[Team])
async def get_teams(session: AsyncSession = Depends(db.get_session)):
    teams = await tmq.get_teams(session)
    teams = [Team.model_validate(t) for t in teams]

    teams = await Resolver().resolve(teams)

    return teams
```

### Day 4

For sprints I just want to return fields of id and name.

```python
class Sprint(DefineSubset):
    __subset__ = (sprint_schema.Sprint, ('id', 'name'))

class Team(DefineSubset)
    __subset__ = (team_schema.Team, ('id', 'name'))

    sprints: Annotated[list[Sprint], LoadBy('id')] = []
    members: Annotated[list[us.User], LoadBy('id')] = []

@route.get('/teams', response_model=List[Team])
async def get_teams(session: AsyncSession = Depends(db.get_session)):
    teams = await tmq.get_teams(session)
    teams = [Team.model_validate(t) for t in teams]

    teams = await Resolver().resolve(teams)

    return teams
```



## Construct complex data with resolve and post

Let's take Agile's model for example, it includes Story, Task and User, here is a [live demo](https://www.newsyeah.fun/voyager/) and [source code](https://github.com/allmonday/composition-oriented-development-pattern/tree/master/src/services)

### 1. Define entities and relationships

Establish entity relationships model based on business concept.

```python
from pydantic import BaseModel

class Story(BaseModel):    
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
```

The dataloader is defined for general usage, if other approach such as ORM relationship is available, it can be easily replaced.
DataLoader's implementation supports all kinds of data sources, from database queries to microservice RPC calls.

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

ErDiagram can help declare the entity relationships, and fastapi-voyager can display it.

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

config_global_resolver(diagram)  # inject into Resolver
```

<img width="758" height="444" alt="image" src="https://github.com/user-attachments/assets/58d95751-2871-40e2-a69a-8a52a2872621" />


### 2. Compose core business data structure.

We can simpliy inherit or use `DefineSubset` to reuse Entity fields and extends new field and resolve them by dataloaders.

[view in voyager](https://www.newsyeah.fun/voyager/?tag=demo&route=src.router.demo.router.get_stories_with_detail)

If ErDiagram is not provided, we need to manually choose the loader:

```python
class Task(BaseTask):
    user: Optional[BaseUser] = None
    def resolve_user(self, loader=Loader(user_batch_loader)):
        return loader.load(self.owner_id) if self.owner_id else None

class Story(BaseStory):
    tasks: list[Task] = []
    def resolve_tasks(self, loader=Loader(story_to_task_loader)):
        return loader.load(self.id)

    assignee: Optional[BaseUser] = None
    def resolve_assignee(self, loader=Loader(user_batch_loader)):
        return loader.load(self.owner_id) if self.owner_id else None
```

If ErDiagram is provided, we just need to provide the name of foreign key

```python
class Task(BaseTask):
    user: Annotated[Optional[BaseUser], LoadBy('owner_id')] = None

class Story(BaseStory):
    tasks: Annotated[list[Task], LoadBy('id')] = []
    assignee: Annotated[Optional[BaseUser], LoadBy('owner_id')] = None        
```

~~`ensure_subset` decorator is a helper function which ensures the target class's fields (without default value) are strictly subset of class in parameter.~~

Meta class `DefineSubset` can be used to define schema with picked fields.

```python
class Story1(DefineSubset):
    # define the base class and fields wanted
    __pydantic_resolve_subset__ = (BaseStory, ('id', 'name', 'owner_id'))

    tasks: Annotated[list[Task1], LoadBy('id')] = []
    assignee: Annotated[Optional[BaseUser], LoadBy('owner_id')] = None
```

### 3. Make additional transformations based on business requirements.

Dataset from base entities can not meet all requirements, adding extra computed fields or adjusting current data are common requirements.

`post_method` is what we need, it is triggered after all descendant nodes are resolved.

It could read fields from ancestor, collect fields from descendants or modify the data fetched by resolve method.

Let's show them case by case.



#### #1: Compute new fields from current data

[view in voyager](https://www.newsyeah.fun/voyager/?tag=demo&route=src.router.demo.router.get_stories_with_detail_2), double click `Story2`

post methods are executed after all resolve_methods are resolved, so we can use it to calculate extra fields.

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

#### #2: Collect items from descendants

[view in voyager](https://www.newsyeah.fun/voyager/?tag=demo&route=src.router.demo.router.get_stories_with_detail_1), double click `Task1`, choose `source code`


`__pydantic_resolve_collect__` can collect fields from current node and then send them to ancestor node who declared `related_users`.

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

#### #3: Propagate ancestor data to descendants through `ancestor_context`

[view in voyager](https://www.newsyeah.fun/voyager/?tag=demo&route=src.router.demo.router.get_stories_with_detail_3), double click `Story3`

`__pydantic_resolve_expose__` could expose specific fields from current node to it's descendant.

alias_names should be global unique inside root node.

descendant nodes could read the value with `ancestor_context[alias_name]`.

[source code](https://github.com/allmonday/composition-oriented-development-pattern/blob/master/src/router/demo/schema3.py)

```python

# post case 1
class Task3(BaseTask):
    user: Annotated[Optional[BaseUser], LoadBy('owner_id')] = None

    fullname: str = ''
    def post_fullname(self, ancestor_context):  # Access story.name from parent context
        return f'{ancestor_context["story_name"]} - {self.name}'

class Story3(DefineSubset):
    __pydantic_resolve_subset__ = (BaseStory, ('id', 'name', 'owner_id'))
    __pydantic_resolve_expose__ = {'name': 'story_name'}

    tasks: Annotated[list[Task3], LoadBy('id')] = []
    assignee: Annotated[Optional[BaseUser], LoadBy('owner_id')] = None
```

### 4. Run with resolver

```python
from pydantic_resolve import Resolver

stories = [Story(**s) for s in await query_stories()]
data = await Resolver().resolve(stories)
```

`query_stories()` returns `BaseStory` list, after we transformed it into `Story`, resolve and post fields are initialized as default value, after `Resolver().resolve()` finished, all these fields will be resolved and post-processed to what we expected.


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
