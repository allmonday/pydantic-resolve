# API

## 方法

### resolve

resolve_field 方法可以是 async 的， Resolver 会递归的解析子节点中的所有 resolve_field 方法来获取数据

可以使用的参数

- context
- ancestor_context
- parent
- dataloaders（支持多个）

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

post_field 方法可以为 sync 或者 async, 在子孙节点的数据处理完毕之后触发，用来对获取到的数据做后续处理。

可以使用的参数:

- context
- ancestor_context
- parent
- dataloaders（支持多个）
- collectors (支持多个)

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

`post_default_handler` 是一个特殊的 post 方法， 他会在所有 post 方法执行完毕之后执行。 适用于处理一些收尾工作。

注意该方法没有自动赋值的逻辑， 需要自己手动指定。

可以使用的参数:

- context
- ancestor_context
- parent
- collectors (支持多个)

```python
class Blog(BaseModel):
    id: int

    length: int

    def post_default_handler(self):
        self.length = 100
```

## Resolver

pydantic-resolve 的执行入口

```python

class Resolver:
    def __init__(
            self,
            loader_params: Optional[Dict[Any, Dict[str, Any]]] = None,
            global_loader_param: Optional[Dict[str, Any]] = None,
            loader_instances: Optional[Dict[Any, Any]] = None,
            context: Optional[Dict[str, Any]] = None):
```

### loader_params

用来提供 DataLoader 的参数

```python
resolver = Resolver(loader_params={ LoaderA: { "param_x": 1, "param_y": 2 } })
```

### global_loader_param

用来全局设置 DataLoader 参数

```python
resolver = Resolver(global_loader_param={ { "param_x": 1, "param_y": 2 } })
```

注意如果参数有多种来源

```python
resolver = Resolver(
    loader_params={ LoaderA: { "param_x": 2 } }, 
    global_loader_param={ { "param_x": 1, "param_y": 2 } })
```

会报错.

### loader_instances

可以传入 DataLoader 实例 （提前写入数据）

```python
loader = LoaderA()
loader.prime('a', [1,2,3])
resolver = Resolver(loader_instances={ LoaderA: loader })
```

### context
提供全局参数, 在所有的 resolve, post 方法中都可以获取到

```python
resolver = Resolver(context={'name': 'tangkikodo'})
```

## 方法参数说明

### context

context 是一个全局上下文， 在 Resolver 方法中设置， 可以被所有方法获取到。

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

在一些场景中， 我们可能需要获取某个节点的祖先节点中的数据， 就可以通过 ancestor_context 来实现

首先你需要在祖先节点中添加 `__pydantic_resolve_expose__` 参数来配置要提供的字段名称和别名（层叠中发生重名）

然后就能通过 ancestor_context 来读取到了。

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

可以获得自己的直接父节点， 在 tree 结构中特别有用。

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

collector 可以用来跨代获取子孙节点的数据， 需要配合 `Collector` 和 `__pydantic_resolve_collect__` 参数使用

在子孙节点中定义 `__pydantic_resolve_collect__` 来指定需要提供的字段信息/收集者名字。

collector 可以让开发者灵活地调整数据结构，不需要去循环地展开子孙节点。

比如， 我们可以在顶层 schema 中收集每个 blog 的 comment 信息。

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

1. collector 支持创建多个
2. `Collector` 默认会使用数组来叠加数据， flat=True 会在内部使用 extend 合并数据
3. 可以继承 `ICollector` 来创建自定义的收集器

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

注意 collector 只能在 post 和 post_default_handler 中使用

post 方法中可以收集 resolve 或者其他对象字段的子孙数据

post_default_handler 可以额外收集 post 方法返回值的子孙数据

### dataloader

DataLoader 可以将并发的多个异步查询合并为一个。

在 pydantic-resolve 中需要使用 LoaderDepend 来管理 DataLoader。

支持一个方法中申明多个 DataLoader。

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

如果 DataLoader 中有定义类变量， 可以在 Resolver 方法中提供参数。

```python hl_lines="2 7"
class LoaderA(DataLoader):
    power: int
    async def batch_load_fn(self, keys: List[int]):
        return [ k** self.power for k in keys ]

data = await Resolver(loader_filters={LoaderA:{'power': 2}}).resolve(data)
```

如果多个相同类型的 DataLoader 使用了相同的参数， 可以使用 `global_loader_param` 来简化设置参数。

请慎用， 参数维护可能会不清晰。

## 辅助方法

### build_list, build_object

在 DataLoader 中用来将获取到的数据根据 keys 做聚合。

build_list 返回对象数组， build_object 返回对象。

签名 `build_list(data, keys, lambda d: d.key)`

### model_config

使用 exclude 可以在 pydantic 转换成目标数据时移除字段， 但是光这么做在 FastAPI 中生成 openapi.json 时 `name` 字段依然会存在于定义中， 添加 model_config() 装饰器可以移除 `name`。

签名 `model_config(default_required=True)`

```python
@model_config()
class Data(BaseModel):
    name: str = Field('', exclude=True)
```

### ensure_subset

签名 `ensure_subset(base_kls)`

如果只需要一部分字段， 但有希望严格确保子集， 可以使用 `ensure_subset` 来检查。

如果 Base 做了变化导致字段不存在， 会抛出 AttributeError

```python
class Base(BaseModel):
    a: str
    b: int

@ensure_subset(Base)
class ChildA(BaseModel):
    a: str
```

### mapper

提供数据转换装饰器

```python
class Data(BaseModel):
    id: int

    items: List[Item] = []

    @mapper(lambda x: do_some_conversion(x))
    def resolve_items(self, loader=LoaderDepend(ItemLoader)):
        return loader.load(self.id)
```

### copy_dataloader_kls

拷贝一份 DataLoader， 用来处理带参数的 DataLoader 需要传递不同参数的情况。

```python
NewLoader = copy_dataloader_kls('NewLoader', OriginLoader)
```

## 异常

- `ResolverTargetAttrNotFound`: 目标 field 不存在
- `LoaderFieldNotProvidedError`: Resolve 中没有提供 Loader 所需的参数
- `GlobalLoaderFieldOverlappedError`: `global_loader_params` 和 `loader_params` 参数出现重复
- `MissingCollector`: 找不到目标 collector, 祖先节点方法中未定义
