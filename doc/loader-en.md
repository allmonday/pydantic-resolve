# Usage of LoaderDepend

## Background introduction

If you have used dataloader, whether in JS or Python, you may encounter a problem: how to create an independent dataloader for each single request?

Taking `strawberry` in Python as an example:

```python
@strawberry.type
class User:
    id: strawberry.ID

async def load_users(keys) -> List[User]:
    return [User(id=key) for key in keys]

loader = DataLoader(load_fn=load_users)

@strawberry.type
class Query:
    @strawberry.field
    async def get_user(self, id: strawberry.ID) -> User:
        return await loader.load(id)

schema = strawberry.Schema(query=Query)
```

If instantiated separately, it will cause all requests to use the same dataloader. Since the loader itself has a caching optimization mechanism, even if the content is updated, it will still return cached historical data.

Therefore, the handling method of `strawberry` is:

```python
@strawberry.type
class User:
    id: strawberry.ID

async def load_users(keys) -> List[User]:
    return [User(id=key) for key in keys]

class MyGraphQL(GraphQL):
    async def get_context(
        self, request: Union[Request, WebSocket], response: Optional[Response]
    ) -> Any:
        return {"user_loader": DataLoader(load_fn=load_users)}


@strawberry.type
class Query:
    @strawberry.field
    async def get_user(self, info: Info, id: strawberry.ID) -> User:
        return await info.context["user_loader"].load(id)

schema = strawberry.Schema(query=Query)
app = MyGraphQL(schema)
```

Developers need to initialize the loader in `get_context`, and the framework will take care of executing the initialization on each request. This ensures that each request has an independent loader, solving the problem of multiple requests being cached.

The principle behind this is that contextvars performs a shallow copy when awaiting, so the outer context can be read by the inner context. Therefore, manually initializing a reference type (dict) at the outermost level (during the request) allows the loader inside the reference type data to be accessed within the request.

While this method is good, there are two problems:

1. It is necessary to manually maintain `get_context`. Whenever a new DataLoader is added, it needs to be added to the context, and the actual execution of `.load` also needs to retrieve the loader from the context.

2. There are situations where loaders are initialized but not used, such as when there are N loaders in the entire query, but the user's query only uses one. This results in wasted initialization of other loaders. Moreover, as the number of shared items increases, code maintenance becomes unclear. (Important)

And graphene is even more capricious, handing over the work of the loader to [aiodataloader](https://github.com/graphql/dataloader#creating-a-new-dataloader-per-request). If you read the documentation, you will find that the processing approach is similar, but manual maintenance of the creation process is required.

## Solution

The functionality I expect is:

1. Initialization should be executed on demand. For example, if only DataLoaderA exists in my entire schema, I hope only DataLoaderA will be instantiated.

2. I do not want to manually maintain initialization in a request or middleware.

In fact, these two things are talking about the same problem, which is how to invert the dependency of initialization to the resolve_field method.

Specifically, it can be translated into code as follows:

```python
class CommentSchema(BaseModel):
    id: int
    task_id: int
    content: str

    feedbacks: List[FeedbackSchema]  = []
    def resolve_feedbacks(self, loader=LoaderDepend(FeedbackLoader)):
        return loader.load(self.id)

class TaskSchema(BaseModel):
    id: int
    name: str

    comments: List[CommentSchema]  = []
    def resolve_comments(self, loader=LoaderDepend(CommentLoader)):
        return loader.load(self.id)
```

That is to say, as long as I declare the loader properly, I don't need to worry about anything else. Can this be achieved?

Thanks to the existence of a manual "resolve" process in `pydantic-resolve`, which leads to the following approach:

1. Contextvars are shallow copies, so if the stored value is a reference type, the dictionary defined at the outermost layer can be read by all inner layers. This can be defined during Resolver initialization.
2. If there are n `tasks: list[TaskSchema]`, I hope to initialize and cache the loader the first time it is encountered, and use the cached loader for subsequent tasks.
3. The LoaderDepend stores the DataLoader class, which is passed as a default parameter to the `resolve_field` method.
4. Before executing `resolve_field`, use `inspect.signature` to analyze the default parameter and execute the initialization and caching logic.

Overall, this is a lazy approach, where the initialization process is handled when actually executed.

In the figure below, 1 initializes LoaderA, while 2 and 3 read from the cache. 1.1 initializes LoaderB, while 2.1 and 3.1 read from the cache.

![img](./imgs/contextvar_cache.png)

code：

```python
class Resolver:
    def __init__(self):
        self.ctx = contextvars.ContextVar('pydantic_resolve_internal_context', default={})
    
    def exec_method(self, method):
        signature = inspect.signature(method)
        params = {}

        for k, v in signature.parameters.items():
            if isinstance(v.default, Depends):
                cache_key = str(v.default.dependency.__name__)
                cache = self.ctx.get()

                hit = cache.get(cache_key, None)
                if hit:
                    instance = hit
                else:
                    instance = v.default.dependency()
                    cache[cache_key] = instance
                    self.ctx.set(cache)

                params[k] = instance
                
        return method(**params)
```


## Outstanding Issues

Some DataLoader implementations may require an external query condition, such as when querying a user's absence information, in addition to the user_key, additional global filters such as sprint_id need to be provided. Passing these global variables through the load parameters can be cumbersome.

In this case, contextvars still need to be used to set variables externally. As an example, consider the following code snippet from a project:

```python
async def get_team_users_load(team_id: int, sprint_id: Optional[int], session: AsyncSession):
    ctx.team_id_context.set(team_id)      # set global filter
    ctx.sprint_id_context.set(sprint_id)  # set global filter

    res = await session.execute(select(User)
                                .join(UserTeam, UserTeam.user_id == User.id)
                                .filter(UserTeam.team_id == team_id))
    db_users = res.scalars()
    users = [schema.UserLoadUser(id=u.id, employee_id=u.employee_id, name=u.name) 
                for u in db_users]

    results = await Resolver().resolve(users)  # resolve
    return results
```

```python
class AbsenseLoader(DataLoader):
    async def batch_load_fn(self, user_keys):
        async with async_session() as session, session.begin():
            sprint_id = ctx.sprint_id_context.get()  # read global filter

            sprint_stmt = Sprint.status == SprintStatusEnum.ongoing if not sprint_id else Sprint.id == sprint_id
            res = await session.execute(select(SprintAbsence)
                                        .join(Sprint, Sprint.id == SprintAbsence.sprint_id)
                                        .join(User, User.id == SprintAbsence.user_id)
                                        .filter(sprint_stmt)
                                        .filter(SprintAbsence.user_id.in_(user_keys)))
            rows = res.scalars().all()
            dct = {}
            for row in rows:
                dct[row.user_id] = row.hours
            return [dct.get(k, 0) for k in user_keys]
```

What we expected to have：

```python
loader_params = {
    AbsenseLoader: {'sprint_id': 10}, 
    OtherLoader: {field: 'value_x'}
}
results = await Resolver(loader_params=loader_params).resolve(users)
```

> If filtering is required but not set, an exception should be thrown.

> translated by GPT3.5