# Reference

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


## Context

pydantic-resolve provides 2 kinds of contexts for different scenarios

### context

context is a global context, after setting it in Resolver, resolve_field and post_field can use `context` param to get it.

```python hl_lines="5 9"
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

```
Blog(id=1, 
     comments=['my-comment-1', 'my-comment-2'], 
     post_comments=['my-comment-2'])
```

### ancestor_context and expose

By using `ancestor_context` param, descendants can read all fields defined in `__pydantic_resolve_expose__` (must be ancestor)

this example shows the blog title can read from it's descendant comment.

```python hl_lines="4 10"
class Comment(BaseModel):
    id: int
    content: str
    def post_content(self, ancestor_context):
        blog_title = ancestor_context['blog_title']
        return f'[{blog_title}] - {self.content}'


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
```

```
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

## Dataloader

### LoaderDepend

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


### loader_params

You are free to define Dataloader with some fields and set these fields with `loader_params` in Resolver

```python hl_lines="2"
class LoaderA(DataLoader):
    power: int
    async def batch_load_fn(self, keys: List[int]):
        return [ k** self.power for k in keys ]

data = [A(val=n) for n in range(3)]
with pytest.warns(DeprecationWarning):
    data = await Resolver(loader_filters={LoaderA:{'power': 2}}).resolve(data)
```


### global_loader_param

If Dataloaders shares some common params, it is possible to declare them by `global_loader_param`

```python hl_lines="39"
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
        data = await Resolver(global_loader_filter={'power': 2}, 
                              loader_filters={LoaderC:{'add': 1}}).resolve(data)
```

### build_list, build_object

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

## Visibility

### model_config
fields with default value will be converted to optional in typescript definition. add model_config decorator to avoid it.

```python
class Y(BaseModel):
    id: int = 0

@model_config()
class Z(BaseModel):
    id: int = 0
```

```ts
interface Y {
    id?: number
}

interface Z {
    id: number
}
```

### Exclude

setting exclude=True will hide these fields, both in serilization and exporting json schema (openapi).

```python hl_lines="9"
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


## Loader instance

to be continue