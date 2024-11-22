# API

## Methods

### resolve

The `resolve_field` method can be async, and the Resolver will recursively resolve all `resolve_field` methods in the child nodes to obtain data.

Usable parameters:

- context
- ancestor_context
- parent
- dataloaders (supports multiple)

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

### post

The `post_field` method can be sync or async, and it is triggered after the data of the descendant nodes is processed, used for subsequent processing of the obtained data.

Usable parameters:

- context
- ancestor_context
- parent
- dataloaders (supports multiple)
- collectors (supports multiple)

```python
class Blog(BaseModel):
    id: int

    comments: list[str] = []
    def resolve_comments(self):
        return ['comment-1', 'comment-2']

    def post_comments(self):
        return self.comments[-1:] # keep the last one
```

### post_default_handler

`post_default_handler` is a special post method that is executed after all post methods are executed. It is used for handling some finishing work.

Note that this method does not have automatic assignment logic, you need to manually specify it.

Usable parameters:

- context
- ancestor_context
- parent
- collectors (supports multiple)

```python
class Blog(BaseModel):
    id: int

    length: int

    def post_default_handler(self):
        self.length = 100
```

## Resolver

The entry point for pydantic-resolve execution

```python

class Resolver:
    def __init__(
            self,
            loader_params: Optional[Dict[Any, Dict[str, Any]]] = None,
            global_loader_param: Optional[Dict[str, Any]] = None,
            loader_instances: Optional[Dict[Any, Any]] = None,
            context: Optional[Dict[str, Any]] = None):
```

- `loader_params`: Used to provide parameters for DataLoader
- `copy_dataloader_kls`: Used to batch set DataLoader parameters
- `loader_instances`: Can pass in DataLoader instances (pre-filled data)
- `context`: Provides global parameters

## Method Parameter Description

### context

`context` is a global context, set in the Resolver method, and can be accessed by all methods.

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

### ancestor_context

In some scenarios, we may need to obtain data from the ancestor nodes of a certain node, which can be achieved through `ancestor_context`.

First, you need to add the `__pydantic_resolve_expose__` parameter in the ancestor node to configure the field names and aliases to be provided (in case of name conflicts in the hierarchy).

Then you can read it through `ancestor_context`.

```python hl_lines="2 18"
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

### parent

You can get your direct parent node, which is particularly useful in tree structures.

```python hl_lines="6-8"
class Tree(BaseModel):
    name: str
    children: List[Tree] = []

    path: str = ''
    def resolve_path(self, parent):
        if parent is not None:
            return f'{parent.path}/{self.name}'
        return self.name

data = dict(name="a", children=[
    dict(name="b", children=[
        dict(name="c")
    ]),
    dict(name="d", children=[
        dict(name="c")
    ])
])
data = await Resolver().resolve(Tree(**data))
```

### collector

`collector` can be used to obtain data from descendant nodes across generations, and it needs to be used in conjunction with `Collector` and the `__pydantic_resolve_collect__` parameter.

Define `__pydantic_resolve_collect__` in the descendant nodes to specify the field information/collector name to be provided.

`collector` allows developers to flexibly adjust the data structure without having to loop through the descendant nodes.

For example, we can collect the comment information of each blog in the top-level schema.

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

1. `collector` supports creating multiple instances
2. `Collector` will use an array to accumulate data by default, `flat=True` will use `extend` to merge data internally
3. You can inherit `ICollector` to create custom collectors

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

collector can only be used in post and post_default_handler

post methods can collect descendant data from resolve or other object fields

post_default_handler can additionally collect descendant data from the return values of post methods.


### dataloader

`DataLoader` can merge multiple concurrent asynchronous queries into one.

In pydantic-resolve, you need to use `LoaderDepend` to manage `DataLoader`.

A method can declare multiple `DataLoader`s.

```python
from pydantic_resolve import LoaderDepend

class Blog(BaseModel):
    id: int
    title: str

    comments: list[Comment] = []
    async def resolve_comments(self,
                         loader1=LoaderDepend(blog_to_comments_loader),
                         loader2=LoaderDepend(blog_to_comments_loader2)):
        v1 = await loader1.load(self.id)  # list
        v2 = await loader2.load(self.id)  # list
        return v1 + v2
```

If the `DataLoader` has class variables defined, you can provide parameters in the `Resolver` method.

```python hl_lines="2 7"
class LoaderA(DataLoader):
    power: int
    async def batch_load_fn(self, keys: List[int]):
        return [ k** self.power for k in keys ]

data = await Resolver(loader_filters={LoaderA:{'power': 2}}).resolve(data)
```

If multiple `DataLoader`s of the same type use the same parameters, you can use `global_loader_param` to simplify the parameter settings.

Use with caution, as parameter maintenance may become unclear.

## Auxiliary Methods

### build_list, build_object

Used in `DataLoader` to aggregate the obtained data according to the keys.

`build_list` returns an array of objects, `build_object` returns an object.

Signature: `build_list(data, keys, lambda d: d.key)`

### model_config

Using `exclude` can remove fields when converting pydantic to the target data, but doing so alone will still keep the `name` field in the definition when generating `openapi.json` in FastAPI. Adding the `model_config()` decorator can remove `name`.

Signature: `model_config(default_required=True)`

```python
@model_config()
class Data(BaseModel):
    name: str = Field('', exclude=True)
```

### ensure_subset

Signature: `ensure_subset(base_kls)`

If only a subset of fields is needed, but you want to strictly ensure the subset, you can use `ensure_subset` to check.

If the Base changes and the field does not exist, an `AttributeError` will be thrown.

```python
class Base(BaseModel):
    a: str
    b: int

@ensure_subset(Base)
class ChildA(BaseModel):
    a: str
```

### mapper

Provides a data conversion decorator

```python
class Data(BaseModel):
    id: int

    items: List[Item] = []

    @mapper(lambda x: do_some_conversion(x))
    def resolve_items(self, loader=LoaderDepend(ItemLoader)):
        return loader.load(self.id)
```

### copy_dataloader_kls

Copies a `DataLoader` to handle cases where different parameters need to be passed to `DataLoader`.

```python
NewLoader = copy_dataloader_kls('NewLoader', OriginLoader)
```

## Exceptions

- `ResolverTargetAttrNotFound`: Target field not found
- `LoaderFieldNotProvidedError`: Required parameters for Loader not provided in Resolve
- `GlobalLoaderFieldOverlappedError`: Duplicate parameters in `global_loader_params` and `loader_params`
- `MissingCollector`: Target collector not found, not defined in ancestor node methods
