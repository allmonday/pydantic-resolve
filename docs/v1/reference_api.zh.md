# 文档

## 概念

Pydantic-resolve 最早受到 GraphQL 和关系型数据库外键的启发， 利用 dataloader 将不同的 Schema/Entity 关联起来， 实现数据自由拼装的目的。

基于 pydantic 的 web 框架， 比如 FastAPI 或者 Django-ninja，可以基于 openapi.json 生成前端 sdk 方便开发。

## Resolve 方法

resolve_field 方法可以是 async 的， Resolver 会递归的解析子节点中的所有 resolve_field 方法来获取数据

可以使用的参数 (参数具体的用途后面会详细说明)

- context
- ancestor_context
- parent
- **dataloaders** (multiple)

样例代码：

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

## Post 方法

post_field 方法可以为 sync 或者 async, 在子孙节点的数据处理完毕之后触发，用来对获取到的数据做后续处理。

可以使用的参数:

- context
- ancestor_context
- parent
- **collectors** (multiple)

使用场景：

1. 修改一个已经获取到的数据

```python
class Blog(BaseModel):
    id: int

    comments: list[str] = []
    def resolve_comments(self):
        return ['comment-1', 'comment-2']

    def post_comments(self):
        return self.comments[-1:] # keep the last one
```

2. 修改一个初始为默认值的数据

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

### post_default_handler 方法

`post_default_handler` 是一个特殊的 post 方法， 他会在所有 post 方法执行完毕之后触发， 适用于对 post 结束之后的数据有依赖的场合。

可以使用的参数:

- context
- ancestor_context
- parent

## 方法参数说明

### Context

> 可以用于全部方法

context 是一个全局上下文， 在 Resolver 方法中设置， 可以被所有方法获取到。

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

输出

```python
Blog(id=1,
     comments=['my-comment-1', 'my-comment-2'],
     post_comments=['my-comment-2'])
```

### Ancestor context

> 可以用于全部方法

在一些场景中， 我们可能需要获取某个节点的祖先节点中的数据， 就可以通过 ancestor_context 来实现

![](./images/expose.jpeg)

首先你需要在祖先节点中添加 `__pydantic_resolve_expose__` 参数来配置要提供的字段名称和别名（层叠中发生重名）

然后就能通过 ancestor_context 来读取到了。

this example shows the blog title can read from it's descendant comment.

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

### Parent

> 可以用于所有方法

可以获得自己的直接父节点， 在 tree 结构中特别有用

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

output

```json hl_lines="3 7 11 18 22"
{
  "name": "a",
  "path": "a",
  "children": [
    {
      "name": "b",
      "path": "a/b",
      "children": [
        {
          "name": "c",
          "path": "a/b/c",
          "children": []
        }
      ]
    },
    {
      "name": "d",
      "path": "a/d",
      "children": [
        {
          "name": "c",
          "path": "a/d/c",
          "children": []
        }
      ]
    }
  ]
}
```

### Collectors

> 可以用于: post

![](./images/collect2.jpeg)

collector 可以用来跨代获取子孙节点的数据， 需要配合 `Collector` 和 `__pydantic_resolve_collect__` 参数使用

在子孙节点中定义 `__pydantic_resolve_collect__` 来指定需要提供的字段信息/收集者名字。

collector 可以让开发者灵活地调整数据结构，不需要去循环地展开子孙节点。

比如， 我们可以在顶层 schema 中收集每个 blog 的 comment 信息, 集中起来。

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

输出的 all_comment 信息

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
3. You can inherit `ICollector` and define your own `Collector`, for example, a counter collector. `self.alias` is always **required**.

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

### Dataloaders

> available in: resolve

`LoaderDepend` is a speical dataloader manager, it also prevent type inconsistent from DataLoader or batch_load_fn.

param: can be DataLoader class or batch_load_fn function.

```python
from pydantic_resolve import LoaderDepend

class Blog(BaseModel):
    id: int
    title: str

    comments: list[Comment] = []
    def resolve_comments(self, loader1=LoaderDepend(blog_to_comments_loader)):
        return loader1.load(self.id)  # return FUTURE
```

Multiple loaders are also supported.

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

## DataLoader

DataLoader is a important component in pydantic-resolve, it helps fetching data level by level.

You can use the params below in Resolver, to configure your loaders.

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

```python hl_lines="2 7 12 40"
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
    data = await Resolver(
        global_loader_filter={'power': 2},
        loader_filters={LoaderC:{'add': 1}}).resolve(data)
```

### Loader instance

You can provide loader instance by `loader_instances`, and `prime` (preload) some data before use, so that internally pydantic-resolve will use it instead of creating from loader class.

```python
loader = SomeLoader()
loader.prime('tangkikodo', ['tom', 'jerry'])
loader.prime('john', ['mike', 'wallace'])
data = await Resolver(loader_instances={SomeLoader: loader}).resolve(data)
```

references: [loader methods](https://github.com/syrusakbary/aiodataloader#primekey-value)

### Build list and object

helper function, use `build_list` for One2Many, use `build_object` for One2One

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

better ts definitions and hide some fields

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
  id?: number; // bad
}

interface Z {
  id: number; // good
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

### ensure_subset(base_kls)

You can create a new pydantic class by copying the original one and keep the fields you wanted.

Decorating it with `ensure_subset` will validate it for you.

```python
class Base(BaseModel):
    a: str
    b: int

@ensure_subset(Base)
class ChildA(BaseModel):
    a: str
```

c is not existed in Base, exception raised.

```python
@util.ensure_subset(Base)
class ChildB(BaseModel):
    a: str
    c: int = 0  # raise AssertionError
```
