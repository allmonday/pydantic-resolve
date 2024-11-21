## What's the most suitable solution for UI integration?

let's talk about a fetching & post-processing solution for building data from simple to complicated.

## First, Start from GraphQL
The major GraphQL flow is like:

```
GraphQL flow = 
            Query 
            -> Parsed Schema 
            -> BFR (Breadth-first resolve) 
            -> data
```

For most scenarios of integration, it has some shortcomings:

- Query is too flexible, need maintenance during iteration
- The Potential of dataloader is limited
- No post process: BFR runs from top to bottom, it miss the stages of from bottom to top.

We'll talk them in details and discuss about how to improve/fix them.

Demos are written in python with libs of `[pydantic, pydantic-resolve]`

### Query is too flexible

`Query` can be harmful.

`Query` is friendly for client but kind of nightmare for server, especially for integrations.

In fact exposing Query interface to client without limitation can always be a bad choose, as a result, server side lost the control of the whole business information/flow, and you’ll always be forced to take client into consideration during debugging. 

It also lost the capability of refactoring for server side because queries are dynamic and difficult to predict the usages in real world, and client can query too much to lower the performance.

As a query language, GraphQL plays pretty if you are not performance sensitive.

As a API, it will be terrible if server do not has full control over the query.

So, it's a reasonable choose to maintain the `Query` at server side (eg: WunderGraph)


### Parsed Schema

Parsed schema is the result of intersection from overall schema and query target.

Comparing to keeping query at service side, keeping the `specific` schemas directly (code first) is more reasonable, and then we don't need to care about the spec of `GraphQL` any more.

- define new schema by inheriting from domain schemas.
- extend new fields with resolve methods.

```python
import blog_service as bs
import comment_service as cs

class MySiteBlog(bs.Blog):  
    comments: list[cs.Comment] = []
    def resolve_comments(self, loader=LoaderDepend(cs.blog_to_comments_loader)):
        return loader.load(self.id)

    comment_count: int = 0
    def post_comment_count(self):
        return len(self.comments)
```


### BFR and dataloader
BFR (breadth-first resolve) is the core process for fetching descendants and at the same time - avoid N+1 query with dataloader.

It resolves level by level, concurrently.

We can run this process manually, to resolve descendants for data.

```python
data = await Resolver().resolve(data)
```

`Dataloader` here is just a simple keys collector, plays as a role of `join` in SQL.

If we want some additional `where` conditions, the interface it not supported.

It would be better if we can define loader like: 

```python
class FeedbackLoader(DataLoader):
    private: bool

    async def batch_load_fn(self, comment_ids):
        async with async_session() as session:
            res = await session.execute(select(Feedback)
                .where(Feedback.private==self.private)
                .where(Feedback.comment_id.in_(comment_ids)))
            rows = res.scalars().all()
            return build_list(rows, comment_ids, lambda x: x.comment_id)
```

and provide `where` fields by:

```python
data = Resolver(
    loader_params={
        FeedbackLoader: {
            'private': private_comment}}).resolve(data)
```

If we can revisit nodes after their descendants are resolve and do additional modifications, it's would be very powerful for constructing UI specific view data.

from simply calculate counts, 
```python
class Blog(BaseModel):
    id: int
    title: str

    comments: list[Comment] = []
    async def resolve_comments(self):
        return await query_comments(self.id)

    comment_count: int = 0
    def post_comment_count(self):
        return len(self.comments)
```

to collect fields (b_name) from descendants:

```python
class A(BaseModel):
    b_list: List[B] = []
    async def resolve_b_list(self):
        return [dict(name='b1'), dict(name='b2')]

    names: List[str] = []
    def post_names(self, collector=SubCollector('b_name')):
        return collector.values()

class B(BaseModel):
    __pydantic_resolve_collect__ = {
        'name': 'b_name',
        'items': 'b_items'
    }
    name: str
    items: List[str] = ['x', 'y']
```


## Then, Start from RESTful
Developers always complain the additional queries in RESTful API: query all comments after blogs are ready. 

Everything get simple after we defined Blog as:

```python
class MySiteBlog(bs.Blog):  
    comments: list[cs.Comment] = []
    def resolve_comments(self, loader=LoaderDepend(cs.blog_to_comments_loader)):
        return loader.load(self.id)

    comment_count: int = 0
    def post_comment_count(self):
        return len(self.comments)
```

and trigger it manually by:

```python
blogs = await get_blogs()
blogs = await Resolver().resolve(blogs)
```

We can inherit the blog schemas and then extends comments for each blog, using dataloader for resolving, looks much like the GraphQL but you can still enjoy all benefits from RESTful. (caching, auth...)


## Conclusion

Compare to GQL, The major different is, these specific schemas are used by each single entry, not reused between entries. So developers can `refactor` one entry without worrying about breaking others.

Another pain point for constructing view data is the gap of structure between persistent layer and a specific view data. Resolving alone can’t overcome that except introducing some new tools to adjust the fetched data during the backward stage of BFT. It can be very very powerful.

I implemented these concepts into a python library named Pydantic-resolve, and using it with FastAPI, immediately I gained the benefits from both GraphQL and restful, also the additionally seamlessly integration experience from openapi-typescript-codegen (hey-api/openapi-ts).
