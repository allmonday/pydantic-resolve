# Use Cases

This document introduces common scenarios for pydantic-resolve and summarizes some development tips.

## Build Data Containers

Define a container structure and query the related data inside it. This is suitable for UI-oriented data composition.

Data at the same level will be fetched concurrently.

```python
from pydantic import BaseModel
from pydantic_resolve import Resolver

class BusinessPage(BaseModel):
    data: List[str] = []
    async def resolve_data(self):
        return await get_data()

    records: List[Record] = []
    async def resolve_records(self):
        return await get_records()

retData = BusinessPage()
retData = await Resolver().resolve(retData)
```

## Build Multi-layer Data

Through inheritance and extension, you can take the return data from a regular RESTful API as the root data, then automatically fetch the required data and apply post-processing according to your definitions.

Separating root data and composition allows you to separate business query logic from data composition logic.

For example, the Company array can be obtained in many ways (by id, ids, filter_by, etc.), yet they can share the same composition.

In addition, using a dataloader can automatically avoid the N+1 query problem.

```python
from pydantic import BaseModel
from pydantic_resolve import Resolver, DoaderDepend

class BaseCompany(BaseModel):
    id: int
    name: str

class Baseffice(BaseModel):
    id: int
    company_id: int
    name: str

class BaseMember(BaseModel):
    id: int
    office_id: int
    name: str

# ------- composition ----------
class Company(BaseCompany):
    offices: List[Office] = []
    def resolve_offices(self, loader=LoaderDepend(OfficeLoader)):
        return loader.load(self.id)

class Office(BaseOffice):
    members: List[Member] = []
    def resolve_members(self, loader=LoaderDepend(MemberLoader)):
        return loader.load(self.id)


raw_companies = [
    BaseCompany(id=1, name='Aston'),
    BaseCompany(id=2, name="Nicc"),
    BaseCompany(id=3, name="Carxx")]

companies = [Company.model_validate(c, from_attributes=True) for c in raw_companies]

data = await Resolver().resolve(companies)
```

## Cross-level Data Passing: Provide Data to Descendants

`__pydantic_resolve_expose__` exposes the current node's data to all of its descendants. In the following example, the Owner's `name` field can be read by its child node Item.

In `{'name': 'owner_name'}`, the key is the field to expose, and the value is a globally unique alias.

If another intermediate node also uses `owner_name`, the Resolver will check this at initialization and raise an error.

Item can access `name` via `ancestor_context` using the globally unique alias `owner_name`.

Both `resolve` and `post` methods can read the `ancestor_context` variable.

```python
from pydantic import BaseModel
from pydantic_resolve import Resolver

class Owner(BaseModel):
    __pydantic_resolve_expose__ = { 'name': 'owner_name' }
    name: str
    items: List[Item]

class Item(BaseModel):
    name: str

    description: str = ''
    def post_description(self, ancestor_context):
        return f'this is item: {self.name}, it belongs to {ancestor_context['owner_name']}'

owners = [
    dict(name="alice", items=[dict(name='car'), dict(name="house")]),
    dict(name="bob", items=[dict(name='shoe'), dict(name="pen")]),
]

owners = await Resolver.resolve([Owner(**o) for o in owners])
```

## Cross-level Data Passing: Send Data to Ancestors

To meet cross-level data collection needs, you can flexibly collect the required data by specifying a collector and specifying the objects to be collected.

Define the data collector in a `post` method, because `resolve` is still in the data fetching stage and information may be incomplete, while `post` is triggered after all descendants have been processed, ensuring completeness.

```python
related_users: list[BaseUser] = []
def post_related_users(self, collector=Collector(alias='related_users')):
    return collector.values()
```

In descendant nodes, provide data by defining `__pydantic_resolve_collect__`. The keys specify which fields to send, and the values are the target collectors.

The key supports tuples to send multiple fields together; the value also supports tuples to send a batch of fields to multiple collectors.

```python
from pydantic_resolve import Loader, Collector

class Task(BaseTask):
    __pydantic_resolve_collect__ = {'user': 'related_users'}  # Propagate user to collector: 'related_users'

    user: Optional[BaseUser] = None
    def resolve_user(self, loader=Loader(UserLoader)):
        return loader.load(self.assignee_id)

class Story(BaseStory):
    tasks: list[Task] = []
    def resolve_tasks(self, loader=Loader(StoryTaskLoader)):
        return loader.load(self.id)

    # ---------- Post-processing ------------
    related_users: list[BaseUser] = []
    def post_related_users(self, collector=Collector(alias='related_users')):
        return collector.values()
```

## Tree-Structured Data Processing

pydantic-resolve provides a `parent` parameter, which allows you to get the parent node.

This parameter makes many functions easy to implement, such as concatenating the full path of a tag.

```python
from pydantic import BaseModel
from pydantic_resolve import Resolver

class Tag(BaseModel):
    name: str

    full_path: str = ''
    def resolve_full_path(self, parent):
        if parent:
            return f'{parent.full_path}/{self.name}'
        else:
            return self.name

    children: List[Tag] = []


tag_data = dict(name='root', children=[
        dict(name='a', children=[
            dict(name='b', children=[
                dict(name='e', chidrent=[])
            ])
        ])
    ])

tag = Tag.parse_obj(tag_data)
tag = await Resolver().resolve(tag)
```

## Hide Unneeded Temporary Variables in Serialized Data

By flexibly combining Pydantic's `Field(exclude=True)` or dataclass's `field(metadata={'exclude': True})`, you can hide intermediate variables that the recipient does not need. These will be filtered out from the serialized result.

## Summary

From another perspective, pydantic-resolve uses structured definitions to constrain the intermediate computation process. By dividing the work into two phases, `resolve` (data fetching) and `post` (post-processing), and with cross-level capabilities of `expose` and `collect`, it provides convenient means for data restructuring between nodes.

The `exclude` capability also prevents intermediate variables from being returned and wasting payload space.

With dataloaders encapsulating implementation details (SQL, NoSQL, or RESTful APIs), data composition can follow ER-model structures. This keeps ER relationships clear throughout the business data processing lifecycle, which is crucial for maintainability.

For relationships like A -> B -> C where you only need A -> C, you can leverage the data persistence layer's implementation (e.g., ORM joins) to build a dataloader directly for A -> C to optimize query performance, avoiding the overhead of traversing A -> B -> C.

Also, a dataloader that returns only BaseClass data enables maximum reuse. For example, a dataloader returning `BaseStory` can serve any subclass that inherits `BaseStory`, or a subset class provided by `@ensure_subset`.

In short, pydantic-resolve provides ample flexibility. Guided by the clarity of the ER model, it helps you obtain the fundamental data needed for computation, then modify and move nodes as required by the business to construct the final result. Over two years of experience shows this pattern saves a lot of code and maintenance cost compared with traditional approaches.
