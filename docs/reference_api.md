# Reference

## Concept

It taks 5 steps to convert from root data into view data.

1. define schema of root data and descdants & load root data
2. forward-resolve all descdants data
3. backward-process the data
4. tree shake the data marked as exclude=True
5. get the output

![](./images/concept.jpeg)

resolve runs level by level:

![](./images/forward.jpeg)

## Fetching

resolve_field, can be async. Resolver will recursively execute `resolve_field` to fetch descendants

```python
class Blog(BaseModel):
    id: int

    comments: list[str] = []
    def resolve_comments(self):
        return ['comment-1', 'comment-2']
    
    tags: list[str] = []
    async def resolve_tags(self):
        await asyncio.sleep(1)
        return ['tag-1', 'tag-2']
```

## Post-process

`post_field`, can only be normal subroutine function. 

You can modify target field after descendants are all resolved.

1) modify a resolved field,
```python
class Blog(BaseModel):
    id: int

    comments: list[str] = []
    def resolve_comments(self):
        return ['comment-1', 'comment-2']
    
    def post_comments(self):
        return self.comments[-1:] # keep the last one
```

2) or modify a new field
```python
class Blog(BaseModel):
    id: int

    comments: list[str] = []
    def resolve_comments(self):
        return ['comment-1', 'comment-2']
    
    comment_count: int = 0
    def post_comment_count(self):
        return len(self.comments)
```


## Contexts

pydantic-resolve provides 3 kinds of contexts for different scenarios

### Context

context is a global context, after setting it in Resolver, resolve_field and post_field can use `context` param to **read** it.

```python hl_lines="5 9 14"
class Blog(BaseModel):
    id: int

    comments: list[str] = []
    def resolve_comments(self, context):
        prefix = context['prefix']
        return [f'{prefix}-{c}' for c in ['comment-1', 'comment-2']]
    
    def post_comments(self, context):
        limit = context['limit']
        return self.comments[-limit:]  # get last [limit] comments
    
blog = Blog(id=1)
blog = await Resolver(context={'prefix': 'my', 'limit': 1}).resolve(blog)
```

output

```python
Blog(id=1, 
     comments=['my-comment-1', 'my-comment-2'], 
     post_comments=['my-comment-2'])
```

### Ancestor context

In some scenario, descendants need to read value from it's direct ancestor.

![](./images/expose.jpeg)

You can use `__pydantic_resolve_expose__` to define the field and it's alias for descendants,
and then read it from `ancestor_context`, using alias as the key.

this example shows the blog title can read from it's descendant comment.

```python hl_lines="2 17"
class Blog(BaseModel):
    __pydantic_resolve_expose__ = {'title': 'blog_title' }
    id: int
    title: str

    comments: list[Comment] = []
    def resolve_comments(self, loader=LoaderDepend(blog_to_comments_loader)):
        return loader.load(self.id)
    
    comment_count: int = 0
    def post_comment_count(self):
        return len(self.comments)

class Comment(BaseModel):
    id: int
    content: str
    def post_content(self, ancestor_context):
        blog_title = ancestor_context['blog_title']
        return f'[{blog_title}] - {self.content}'
```

```json hl_lines="9 13 24 28"
{
    "blogs": [
        {
            "id": 1,
            "title": "what is pydantic-resolve",
            "comments": [
                {
                    "id": 1,
                    "content": "[what is pydantic-resolve] - its interesting"
                },
                {
                    "id": 2,
                    "content": "[what is pydantic-resolve] - i dont understand"
                }
            ],
            "comment_count": 2
        },
        {
            "id": 2,
            "title": "what is composition oriented development pattarn",
            "comments": [
                {
                    "id": 3,
                    "content": "[what is composition oriented development pattarn] - why? how?"
                },
                {
                    "id": 4,
                    "content": "[what is composition oriented development pattarn] - wow!"
                }
            ],
            "comment_count": 2
        }
    ]
}
```

### Collector

![](./images/collect2.jpeg)

Another scenario, ancestor nodes may want to collect some specific fields from it's descendants, where you can use `Collector` and `__pydantic_resolve_collect__`.

> Collector can only be used in post methods, it happens in reverse traversal stages

for example, let's collect all comments into all_comments at top level:

```python hl_lines="13 18"
form pydantic_resolve import Collector

class MyBlogSite(BaseModel):
    blogs: list[Blog] = []
    async def resolve_blogs(self):
        return await get_blogs()

    comment_count: int = 0
    def post_comment_count(self):
        return sum([b.comment_count for b in self.blogs])

    all_comments: list[Comment] = []
    def post_all_comments(self, collector=Collector(alias='blog_comments', flat=True)):
        return collector.values()

class Blog(BaseModel):
    __pydantic_resolve_expose__ = {'title': 'blog_title' }
    __pydantic_resolve_collect__ = {'comments': 'blog_comments' }
    id: int
    title: str

    comments: list[Comment] = []
    def resolve_comments(self, loader=LoaderDepend(blog_to_comments_loader)):
        return loader.load(self.id)
    
    comment_count: int = 0
    def post_comment_count(self):
        return len(self.comments)

class Comment(BaseModel):
    id: int
    content: str
    def post_content(self, ancestor_context):
        blog_title = ancestor_context['blog_title']
        return f'[{blog_title}] - {self.content}'
```

output of all_comments fields:
```json
{
    "other fields": ...,
    "all_comments": [
        {
            "id": 1,
            "content": "[what is pydantic-resolve] - its interesting"
        },
        {
            "id": 2,
            "content": "[what is pydantic-resolve] - i dont understand"
        },
        {
            "id": 3,
            "content": "[what is composition oriented development pattarn] - why? how?"
        },
        {
            "id": 4,
            "content": "[what is composition oriented development pattarn] - wow!"
        }
    ]
}
```

values of `__pydantic_resolve_collect__` must be global unique, this means it is not available in tree structure.

**Usages**:

1. Using multiple collectors is of course supported
```python
def post_all_comments(self, 
                      collector=Collector(alias='blog_comments', flat=True),
                      collector_2=Collector(alias='comment_content', flat=True)):
    return collector.values()
```

2. Using `flat=True` will cal `list.extend` inside, use it if your source field is `List[T]`
3. You can inherit `ICollector` and define your own `Collector`, for example, a counter collector. `self.alias` is **required**.
```python
from pydantic_resolve import ICollector

class CounterCollector(ICollector):
    def __init__(self, alias):
        self.alias = alias
        self.counter = 0

    def add(self, val):
        self.counter = self.counter + len(val)
    
    def values(self):
        return self.counter
```



## Dataloader

### Loader Depend

LoaderDepend(param) is a speical dataloader manager, it also prevent type inconsistent from DataLoader or batch_load_fn.

param: can be DataLoader class or batch_load_fn function.


```python
class Blog(BaseModel):
    id: int
    title: str

    comments: list[Comment] = []
    def resolve_comments(self, loader=LoaderDepend(blog_to_comments_loader)):
        return loader.load(self.id)
```


### Loader params

You are free to define Dataloader with some fields and set these fields with `loader_params` in Resolver

You can treat dataloader like `JOIN` condition, and params like `Where` conditions
```sql
select children from parent 
    # loader keys
    join children on parent.id = children.pid  
    # loader params
    where children.age < 20  
```

```python hl_lines="2 7"
class LoaderA(DataLoader):
    power: int
    async def batch_load_fn(self, keys: List[int]):
        return [ k** self.power for k in keys ]

data = await Resolver(loader_filters={
    LoaderA:{'power': 2}
    }).resolve(data)
```


### Global loader param

If Dataloaders shares some common params, it is possible to declare them by `global_loader_param`

```python hl_lines="40"
class LoaderA(DataLoader):
    power: int
    async def batch_load_fn(self, keys: List[int]):
        return [ k** self.power for k in keys ]

class LoaderB(DataLoader):
    power: int
    async def batch_load_fn(self, keys: List[int]):
        return [ k** self.power for k in keys ]

class LoaderC(DataLoader):
    power: int
    async def batch_load_fn(self, keys: List[int]):
        return [ k** self.power + self.add for k in keys ]

async def loader_fn_a(keys):
    return [ k**2 for k in keys ]

class A(BaseModel):
    val: int

    a: int = 0
    def resolve_a(self, loader=LoaderDepend(LoaderA)):
        return loader.load(self.val)

    b: int = 0
    def resolve_b(self, loader=LoaderDepend(LoaderB)):
        return loader.load(self.val)

    c: int = 0
    def resolve_c(self, loader=LoaderDepend(LoaderC)):
        return loader.load(self.val)


@pytest.mark.asyncio
async def test_case_0():
    data = [A(val=n) for n in range(3)]
    with pytest.warns(DeprecationWarning):
        data = await Resolver(
            global_loader_filter={'power': 2}, 
            loader_filters={LoaderC:{'add': 1}}).resolve(data)
```

### Loader instance

You can provide loader instance by `loader_instances`, so that internally pydantic-resolve will use it instead of creating from loader class.

```python
loader = SomeLoader()
loader.prime('tangkikodo', ['tom', 'jerry'])
loader.prime('john', ['mike', 'wallace'])
data = await Resolver(loader_instances={SomeLoader: loader}).resolve(data)
```

references: [loader methods](https://github.com/syrusakbary/aiodataloader#primekey-value)


### Build list and object

helper function, use `build_list` for O2M, use `build_object` for O2O

```python
async def members_batch_load_fn(team_ids):
    """ return members grouped by team_id """
    _members = member_service.batch_query_by_team_ids(team_ids)

    return build_list(_members, team_ids, lambda t: t['team_id'])  # helper func
```

source code:

```python
def build_list(items: Sequence[T], keys: List[V], get_pk: Callable[[T], V]) -> Iterator[List[T]]:
    """
    helper function to build return list data required by aiodataloader
    """
    dct: DefaultDict[V, List[T]] = defaultdict(list) 
    for item in items:
        _key = get_pk(item)
        dct[_key].append(item)
    results = (dct.get(k, []) for k in keys)
    return results
```

```python
def build_object(items: Sequence[T], keys: List[V], get_pk: Callable[[T], V]) -> Iterator[Optional[T]]:
    """
    helper function to build return object data required by aiodataloader
    """
    dct: Mapping[V, T] = {}
    for item in items:
        _key = get_pk(item)
        dct[_key] = item
    results = (dct.get(k, None) for k in keys)
    return results
```

### Tips

Get information of loaders after resolved.

```python
resolver = Resolver()
data = await resolver.resolve(data)
print(resolver.loader_instance_cache)
```


## Visibility

### model_config
fields with default value will be converted to optional in typescript definition. add model_config decorator to avoid it.

```python hl_lines="4"
class Y(BaseModel):
    id: int = 0

@model_config()
class Z(BaseModel):
    id: int = 0
```

```ts
interface Y {
    id?: number // bad
}

interface Z {
    id: number // good
}
```

### Exclude

setting exclude=True will hide these fields, both in serilization and exporting json schema (openapi).

```python hl_lines="1 9"
@model_config()
class Y(BaseModel):
    id: int = 0
    def resolve_id(self):
        return 1

    name: str = Field(exclude=True)

    password: str = Field(default="", exclude=True)
    def resolve_password(self):
        return 'confidential'
```
