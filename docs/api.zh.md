# API

## 方法

### resolve

resolve_field 方法可以是 async 的， Resolver 会递归的解析子节点中的所有 resolve_field 方法来获取数据

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

可以使用的参数

- context: 全局参数， 在 Resolver 中设置
- ancestor_context：局部参数， 在`__pydantic_resolve_expose__` 中设置
- parent：父节点
- dataloader：允许申明多个 dataloader，形如 `loader=Loader(SomeLoader), loader_b=Loader(AnotherLoader)`


### post

post_field 方法可以为 sync 或者 async, 在子孙节点的数据处理完毕之后触发，用来对获取到的数据做后续处理。

```python
class Blog(BaseModel):
    id: int

    comments: list[str] = []
    def resolve_comments(self):
        return ['comment-1', 'comment-2']

    def post_comments(self):
        return self.comments[-1:] # keep the last one
```

可以使用的参数:

- context: 全局参数， 在 Resolver 中设置
- ancestor_context：局部参数， 在`__pydantic_resolve_expose__` 中设置
- parent：父节点
- dataloader：允许申明多个 dataloader，形如 `loader=Loader(SomeLoader), loader_b=Loader(AnotherLoader)`
    - 注意post 中返回的对象不会被继续递归 resolve， 这点和 resolve 中不同
- collector: 允许申明多个 collector， 形如 `collector_a=Collector('a'), collector_b=Collector('b')`


### post_default_handler

`post_default_handler` 是一个特殊的 post 方法， 他会在所有 post 方法执行完毕之后执行。 适用于处理一些收尾工作。

注意该方法没有自动赋值的逻辑， 需要自己手动指定。

```python
class Blog(BaseModel):
    id: int

    length: int

    def post_default_handler(self):
        self.length = 100
```


可以使用的参数:

- context: 全局参数， 在 Resolver 中设置
- ancestor_context：局部参数， 在`__pydantic_resolve_expose__` 中设置
- parent：父节点
- collector: 允许申明多个 collector， 形如 `collector_a=Collector('a'), collector_b=Collector('b')`

## Resolver

pydantic-resolve 的执行入口

```python

class Resolver:
    def __init__(
            self,
            loader_params: Optional[Dict[Any, Dict[str, Any]]] = None,
            global_loader_param: Optional[Dict[str, Any]] = None,
            loader_instances: Optional[Dict[Any, Any]] = None,
            context: Optional[Dict[str, Any]] = None
            debug: bool = False
            enable_from_attribute_in_type_adapter = False,
            annotation: Optional[Type[T]] = None
            ):
```

### loader_params

用来提供 DataLoader 的参数

```python
resolver = Resolver(loader_params={ LoaderA: { "param_x": 1, "param_y": 2 } })
```

### global_loader_param

用来全局设置 DataLoader 参数， 某些场景下会比较方便。

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

### debug

debug = True 将会开启 logger 输出每个节点的计算总耗时

> export PYDANTIC_RESOLVE_DEBUG=true 可以全局开启

```shell
# sample
Tree          : avg: 1.1ms, max: 1.1ms, min: 1.1ms
Tree.Tree     : avg: 0.4ms, max: 0.5ms, min: 0.4ms
Tree.Tree.Tree: avg: 0.2ms, max: 0.2ms, min: 0.2ms

# sample
MyBlogSite             : avg: 1.5ms, max: 1.5ms, min: 1.5ms
MyBlogSite.Blog        : avg: 1.0ms, max: 1.0ms, min: 1.0ms
MyBlogSite.Blog.Comment: avg: 0.3ms, max: 0.3ms, min: 0.3ms
```

### enable_from_attribute_in_type_adapter (pydantic v2)

只在 pydantic v2 中使用， 主要解决（兜底）从 v1 升级过来可能产生的问题.

> export PYDANTIC_RESOLVE_ENABLE_FROM_ATTRIBUTE=true 可以全局开启

在 v1 中， 从一个 pydantic 对象， 这个对象不是目标字段类型（但是能满足目标类型的所需字段），是可以被 `parse_obj_as` 方法转换成目标字段的， 但是在 v2 中 type adapter 会报错

```python
class A(BaseModel):
  name: str
  id: int

class B(BaseModel):
  name: str
```

v2 中可以通过 `typeAdapter.validate_python(data, from_attribute=True)` 进行兜底，但该方法会对数据转换产生 10%+的性能影响， 因此默认为 False， 按需启用

### annotation
指定解析数据时的根类。 当输入数据是 Union 类型的列表时， 无法自动推断出根类， 这时可以通过该参数来指定根类。


## ErDiagram

ErDiagram 允许你在领域模型层申明应用层的实体关系， 然后基于这些关系自动生成 resolve 方法。

### 核心类

#### Relationship

定义两个实体之间的单一关系。

```python
from pydantic_resolve import Relationship

class User(BaseModel):
    id: int
    name: str

class Comment(BaseModel):
    id: int
    user_id: int

    # 定义关系：通过 user_id 加载 User
    __relationships__ = [
        Relationship(field='user_id', field_name='user', target_kls=User, loader=user_loader)
    ]
```

**参数：**

- `field` (str): 外键字段名
- `target_kls` (type): 目标 Pydantic 模型类
- `field_name` (str): 唯一标识符，将成为 GraphQL 字段名（必填）
- `loader` (Callable): DataLoader 函数，用于获取目标实体
- `field_fn` (Callable | None): 可选函数，在传递给 loader 之前转换 FK 值
- `field_none_default` (Any | None): 当 FK 为 None 时返回的默认值
- `field_none_default_factory` (Callable | None): 当 FK 为 None 时创建默认值的工厂函数
- `load_many` (bool): FK 字段本身是否包含多个值（如 `user_ids: list[int]`），为 True 时内部调用 `loader.load_many()` 而非 `loader.load()`（默认: False）
- `load_many_fn` (Callable | None): 将 FK 字段值转换为可迭代对象的函数，用于 load_many

**注意：** `MultipleRelationship` 和 `Link` 已被移除。现在可以通过创建多个具有相同 `field` 但不同 `field_name` 的 `Relationship` 来实现多重关系。

#### Entity

定义实体元数据，包括其关系。

```python
from pydantic_resolve import Entity

Entity(
    kls=Comment,
    relationships=[
        Relationship(field='user_id', field_name='user', target_kls=User, loader=user_loader)
    ]
)
```

**参数：**

- `kls` (type[BaseModel]): Pydantic 模型类
- `relationships` (list[Relationship]): 关系列表

#### ErDiagram

所有实体关系定义的容器。

```python
from pydantic_resolve import ErDiagram

ErDiagram(
    configs=[
        Entity(kls=Comment, relationships=[...]),
        Entity(kls=User, relationships=[...])
    ],
    description="我的应用 ERD"
)
```

**参数：**

- `configs` (list[Entity]): 实体定义列表
- `description` (str | None): 可选的图表描述

**使用方法：**

要使用 `ErDiagram` 与 Resolver 配合，你需要使用 `config_resolver()` 或 `config_global_resolver()` 注册它：

- `config_resolver(diagram)`: 创建一个带有 ERD 的新自定义 Resolver 类
- `config_global_resolver(diagram)`: 将 ERD 注入到默认 Resolver 类中

详见下面的 [辅助函数](#辅助函数) 部分查看详细使用示例。

### 辅助函数

#### base_entity()

创建一个基类，自动从其子类收集所有实体关系。

**注意：** `BaseEntity` 提供了另一种 ERD 申明方式，与显式创建 `ErDiagram` 对象不同。这种方式与实体类的集成更紧密，使得直接在类定义中管理关系变得更加容易。

```python
from pydantic_resolve import base_entity, Relationship

BaseEntity = base_entity()

class User(BaseModel, BaseEntity):
    id: int
    name: str

    __relationships__ = [
        Relationship(field='org_id', field_name='organization', target_kls=Organization, loader=org_loader)
    ]

class Comment(BaseModel, BaseEntity):
    id: int
    user_id: int

    __relationships__ = [
        Relationship(field='user_id', field_name='user', target_kls=User, loader=user_loader)
    ]

# 获取 ER 图
diagram = BaseEntity.get_diagram()
```

**处理循环引用**

因为实体通过 `target_kls` 相互引用，你可能会遇到循环引用问题。有两种解决方案：

1. **使用字符串引用**（用于同模块引用）：
   ```python
   class Comment(BaseModel, BaseEntity):
       id: int
       user_id: int

       __relationships__ = [
           # 字符串 'User' 会被自动解析
           Relationship(field='user_id', field_name='user', target_kls='User', loader=user_loader)
       ]
   ```

2. **使用模块路径语法**（用于跨模块引用）：
   ```python
   # 在 app/models/comment.py 中

   class Comment(BaseModel, BaseEntity):
       id: int
       user_id: int

       __relationships__ = [
           # 引用另一个模块中的 User
           Relationship(
               field='user_id',
               field_name='user',
               target_kls='app.models.user:User',  # 模块路径:类名
               loader=user_loader
           )
       ]
   ```

`_resolve_ref` 函数支持：

- 简单类名：`'User'`（在当前模块中查找）
- 模块路径语法：`'app.models.user:User'`（从任何模块懒加载）
- 列表泛型：`list['User']` 或 `list['app.models.user:User']`

#### AutoLoad

基于 ERD 关系自动解析字段的注解。

```python
from pydantic_resolve import AutoLoad, base_entity, config_global_resolver

# 1. 使用 BaseEntity 定义实体
BaseEntity = base_entity()

class User(BaseModel, BaseEntity):
    id: int
    name: str
    __relationships__ = [
        Relationship(field='org_id', field_name='organization', target_kls=Organization, loader=org_loader)
    ]

# 2. 全局注册 ERD
config_global_resolver(BaseEntity.get_diagram())

# 3. 在响应模型中使用 AutoLoad
class UserResponse(BaseModel):
    id: int
    name: str

    # 通过 ERD 关系自动解析
    organization: Annotated[Optional[Organization], AutoLoad('org_id')] = None
```

**参数：**

- `key` (str): 外键字段名
- `field_name` (str | None): Relationship 的字段标识符（当同一字段有多个关系时使用）

**注意：** `AutoLoad` 需要与 `config_global_resolver()` 配合，将 ERD 注入到默认 Resolver。

#### config_resolver()

创建带有特定 ERD 配置的新 Resolver 类。

```python
from pydantic_resolve import config_resolver, ErDiagram, Entity

diagram = ErDiagram(configs=[...])
CustomResolver = config_resolver(diagram)

result = await CustomResolver().resolve(data)
```

#### config_global_resolver()

将 ERD 全局注入到默认 Resolver 类中。

```python
from pydantic_resolve import config_global_resolver, base_entity

BaseEntity = base_entity()
# ... 定义实体 ...

config_global_resolver(BaseEntity.get_diagram())

# 现在默认 Resolver 会使用这个 ERD
result = await Resolver().resolve(data)
```

### 高级：处理 None FK 值

当外键为 None 时，你可以指定返回什么：

```python
Relationship(
    field='user_id',
    target_kls=User,
    loader=user_loader,
    field_none_default=None,  # 或
    field_none_default_factory=lambda: AnonymousUser()
)
```

使用 `load_many` 时：

```python
Relationship(
    field='tag_ids',
    target_kls=Tag,
    loader=tag_loader,
    load_many=True,
    load_many_fn=lambda ids: ids.split(',') if ids else []  # 处理逗号分隔的值
)
```

### 高级：多重关系

当一个字段可以表示不同的事物时，创建多个具有相同 `field` 但不同 `field_name` 的 `Relationship`：

```python
class Comment(BaseModel, BaseEntity):
    id: int
    user_id: int  # 可以是 author 或 moderator

    __relationships__ = [
        Relationship(field='user_id', field_name='author', target_kls=User, loader=user_loader),
        Relationship(field='user_id', field_name='moderator', target_kls=User, loader=moderator_loader)
    ]

class CommentResponse(BaseModel):
    id: int

    # 通过 'field_name' 参数指定使用哪个关系
    author: Annotated[Optional[User], AutoLoad('user_id', field_name='author')] = None
    moderator: Annotated[Optional[User], AutoLoad('user_id', field_name='moderator')] = None
```


## DefineSubset & SubsetConfig

`DefineSubset` 允许你从现有 Pydantic 模型创建字段子集，继承类型和验证器。

### 基础用法

```python
from pydantic_resolve import DefineSubset

class FullUser(BaseModel):
    id: int
    name: str
    email: str
    password_hash: str
    created_at: datetime
    updated_at: datetime

class UserSummary(DefineSubset):
    __subset__ = (FullUser, ('id', 'name', 'email'))
```

### 使用 SubsetConfig

如需更多控制，使用 `SubsetConfig`：

```python
from pydantic_resolve import DefineSubset, SubsetConfig
from pydantic_resolve import ExposeAs, SendTo

class UserProfile(DefineSubset):
    __subset__ = SubsetConfig(
        kls=FullUser,
        fields=['id', 'name', 'email'],
        expose_as=[('name', 'user_name')],  # 暴露给后代节点
        send_to=[('id', 'user_id_collector')],  # 发送到父节点的收集器
        excluded_fields=['email']  # 标记为从序列化中排除
    )
```

**SubsetConfig 参数：**

- `kls` (type[BaseModel]): 要从中提取子集的父类
- `fields` (list[str] | "all" | None): 要包含的字段（与 omit_fields 互斥）
- `omit_fields` (list[str] | None): 要排除的字段（与 fields 互斥）
- `expose_fields` (list[str] | None): 通过 ExposeAs 暴露给后代节点的字段
- `excluded_fields` (list[str] | None): 标记为排除的字段（Field(exclude=True)）


## ExposeAs & SendTo

从 v2.3.0 开始，你可以使用注解而不是类属性来进行 expose 和 collect 操作。

### ExposeAs

将字段数据暴露给后代节点。

```python
from pydantic_resolve import ExposeAs

# 之前（类属性）
class Blog(BaseModel):
    __pydantic_resolve_expose__ = {'title': 'blog_title' }
    title: str

# 之后（注解）
class Blog(BaseModel):
    title: Annotated[str, ExposeAs('blog_title')]
```

### SendTo

将字段数据发送到父节点的收集器。

```python
from pydantic_resolve import SendTo

# 之前（类属性）
class Blog(BaseModel):
    __pydantic_resolve_collect__ = {'comments': 'blog_comments' }
    comments: list[Comment]

# 之后（注解）
class Blog(BaseModel):
    comments: Annotated[list[Comment], SendTo('blog_comments')]
```

### 组合使用

你可以组合多个注解：

```python
from pydantic_resolve import ExposeAs, SendTo, AutoLoad

class Comment(BaseModel):
    owner: Annotated[
        Optional[User],
        AutoLoad('user_id'),      # 通过 ERD 自动解析
        SendTo('related_users') # 发送到父节点的收集器
    ] = None

class Blog(BaseModel):
    name: Annotated[str, ExposeAs('blog_name')]  # 暴露给后代节点
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

**从 v2.3.0 开始， 可以使用 `ExposeAs` 来简化 expose 申明**, 注意两种形式不允许共存。

```python
from pydantic_resolve import ExposeAs

class Blog(BaseModel):
    # __pydantic_resolve_expose__ = {'title': 'blog_title' }
    id: int
    title: Annotated[str, ExposeAs('blog_title')]
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

**从 v2.3.0 开始， 可以使用 `SendTo` 来简化 `__pydantic_resolve_collect__` 定义**, 注意两种形式不允许共存。

```python
from pydantic_resolve import ExposeAs, SendTo

class Blog(BaseModel):
    # __pydantic_resolve_expose__ = {'title': 'blog_title' }
    # __pydantic_resolve_collect__ = {'comments': 'blog_comments' }
    id: int
    title: Annotated[str, ExposeAs('blog_title')]

    comments: Annotated[list[Comment], SendTo('blog_comments')] = []
    def resolve_comments(self, loader=LoaderDepend(blog_to_comments_loader)):
        return loader.load(self.id)
```

### dataloader

DataLoader 可以将并发的多个异步查询合并为一个。

在 pydantic-resolve 中需要使用 LoaderDepend 来管理 DataLoader。

> 从 v1.12.5 开始， 你也可以使用 `Loader`， 两者是等价的。

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

#### self.\_query_meta

它提供了 `fields` 和 `request_types` 两个字段信息， 用来获取调用 dataloader 之后用来返回的类型信息。

可以优化 dataloader 中字段范围的限定， 比如 sql 查询中的字段等

因为一个 dataloader 可能有多个调用者， 所以 request_types 类型是个数组

`fields` 是 `request_types.fields` 的去重结果

```python
class SampleLoader(DataLoader):
    async def batch_load_fn(self, keys):
        print(self._query_meta['fields']) # => ['id', 'name']
        print(self._query_meta['request_types']) # => [ {'name': Student, 'fields': ['id', 'name'] } ]

        data = await query_students(self._query_meta['fields'], keys)
        # select id, name from xxxxx

        return build_list(data, keys, lambda d: d.id)

class Student(BaseModel):
    id: int
    name: str

class ClassRoom(BaseModel):
    id: int
    name: str

    students: List[Student] = []
    def resolve_students(self, loader=LoaderDepend(SampleLoader)):
        return loader.load(self.id)
```

#### self._context

DataLoader 可以通过声明 `_context` 属性来访问 Resolver 的全局上下文。这对于权限过滤等场景非常有用（如传递 `user_id`）。

```python
class UserLoader(DataLoader):
    _context: dict  # 声明需要 context

    async def batch_load_fn(self, keys):
        user_id = self._context.get('user_id')
        # 使用 user_id 进行权限过滤
        users = await query_users_with_permission(keys, user_id)
        return users


class TaskResponse(BaseModel):
    id: int
    owner_id: int
    owner: Optional[User] = None

    def resolve_owner(self, loader=LoaderDepend(UserLoader)):
        return loader.load(self.owner_id)

# 提供 context 给 Resolver
resolver = Resolver(context={'user_id': 123})
result = await resolver.resolve(tasks)
```

如果 DataLoader 声明了 `_context` 但 Resolver 没有提供 context，将抛出 `LoaderContextNotProvidedError` 异常。

## 辅助方法

### build_list, build_object

在 DataLoader 中用来将获取到的数据根据 keys 做聚合。

build_list 返回对象数组， build_object 返回对象。

签名 `build_list(data, keys, lambda d: d.key)`

### model_config

> **已弃用**：此装饰器已不推荐使用。请改用 `serialization` 来更好地处理嵌套的 Pydantic 模型。

这个装饰器用来改善 FastAPI 等 web frameworb 根据 response_model 生成 json schema 时存在的问题。

使用 exclude 可以在 pydantic 转换成目标数据时移除字段， 但是光这么做在 FastAPI 中生成 openapi.json 时 `name` 字段依然会存在于定义中， 添加 model_config() 装饰器可以移除 `name`。

签名 `model_config(default_required=True)`

```python
@model_config()
class Data(BaseModel):
    name: str = Field(default='', exclude=True)
```

```python
from pydantic.dataclasses import dataclass

@dataclass
class Car:
    name: str
    used_years: int = field(default=0, metadata={'exclude': True})
```

注意，如果 FastAPI 中使用的是 pydantic v2， 它内部已经做了类似的处理，因此可以不使用 model_config 装饰器.

### serialization

用于递归处理嵌套 Pydantic BaseModel 字段的 JSON schema 装饰器。

这是 `model_config` 的推荐替代方案。它支持：
- 单层嵌套
- 多层嵌套（3层以上）
- 列表嵌套（`List[Model]`）
- 可选字段（`Optional[Model]` 或 `Model | None`）
- 递归字段排除（`exclude=True`）

只需应用于根类，它会自动处理所有嵌套模型。

```python
from pydantic_resolve import serialization
from typing import List, Optional

class Address(BaseModel):
    street: str = ''
    city: str = ''

class Person(BaseModel):
    name: str = ''
    address: Optional[Address] = None

@serialization
class Response(BaseModel):
    person: Person
    items: List[Item]

# 生成 schema
schema = Response.model_json_schema(mode='serialization')
```

**与 `model_config` 的主要区别：**
- 自动递归处理嵌套的 Pydantic 模型
- 只需应用于根类
- 支持复杂的嵌套场景（List、Optional、多层）
- 在所有层级正确设置 `required` 字段并排除 `exclude=True` 的字段

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

## MCP Server

pydantic-resolve 提供 MCP (Model Context Protocol) 服务器支持，允许 AI 代理通过渐进式披露机制发现和交互 GraphQL API。

### create_mcp_server

创建一个 MCP 服务器，将多个 ErDiagram 应用暴露为独立的 GraphQL 端点。

```python
from pydantic_resolve import create_mcp_server, AppConfig

mcp = create_mcp_server(
    apps: List[AppConfig],
    name: str = "Pydantic-Resolve GraphQL API",
) -> "FastMCP"
```

**参数：**

- `apps` (list[AppConfig]): 应用配置列表。每个配置包括：
  - `name`: 应用名称（必填）
  - `er_diagram`: ErDiagram 实例（必填）
  - `description`: 应用描述（可选）
  - `query_description`: Query 类型描述（可选）
  - `mutation_description`: Mutation 类型描述（可选）
  - `enable_from_attribute_in_type_adapter`: 启用 Pydantic from_attributes 模式（默认：False）
- `name` (str): MCP 服务器名称（默认："Pydantic-Resolve GraphQL API"）

**返回：**

一个配置好的 FastMCP 服务器实例，可直接运行。

**示例：**

```python
from pydantic_resolve import base_entity, config_global_resolver, create_mcp_server, AppConfig

# 定义实体
BaseEntity = base_entity()

class User(BaseModel, BaseEntity):
    id: int
    name: str

class Comment(BaseModel, BaseEntity):
    id: int
    user_id: int
    __relationships__ = [
        Relationship(field='user_id', field_name='user', target_kls=User, loader=user_loader)
    ]

config_global_resolver(BaseEntity.get_diagram())

# 创建包含多个应用的 MCP 服务器
apps = [
    AppConfig(
        name="blog",
        er_diagram=BaseEntity.get_diagram(),
        description="博客系统，包含用户和文章",
    ),
    AppConfig(
        name="shop",
        er_diagram=shop_diagram,
        description="电商系统",
    )
]

mcp = create_mcp_server(apps=apps, name="My API")

# 运行服务器
mcp.run(transport="streamable-http", port=8080)
```

### AppConfig

MCP 服务器中 GraphQL 应用的配置类。

```python
from pydantic_resolve import AppConfig

AppConfig(
    name: str,                    # 应用名称（必填）
    er_diagram: ErDiagram,        # ErDiagram 实例（必填）
    description: str | None = None,
    query_description: str | None = None,
    mutation_description: str | None = None,
    enable_from_attribute_in_type_adapter: bool = False,
)
```

**参数：**

| 参数 | 类型 | 描述 |
|------|------|------|
| `name` | str | 应用名称，用于标识 GraphQL 端点 |
| `er_diagram` | ErDiagram | 包含实体定义的 ErDiagram 实例 |
| `description` | str \| None | 可选的应用描述 |
| `query_description` | str \| None | Query 类型的可选描述 |
| `mutation_description` | str \| None | Mutation 类型的可选描述 |
| `enable_from_attribute_in_type_adapter` | bool | 启用 Pydantic from_attributes 模式，允许 loader 返回 Pydantic 实例而不是字典 |

### 运行 MCP 服务器

FastMCP 的 `mcp.run()` 方法支持多种传输模式：

```python
# HTTP 传输，自定义端口
mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)

# SSE (Server-Sent Events) 传输
mcp.run(transport="sse", port=8080)

# stdio 传输（用于 Claude Desktop，无需端口）
mcp.run(transport="stdio")
```

**常用参数：**

| 参数 | 描述 | 默认值 |
|------|------|--------|
| `transport` | 传输模式：`"stdio"`、`"streamable-http"`、`"sse"` | `"stdio"` |
| `host` | 绑定的主机地址 | `"127.0.0.1"` |
| `port` | 端口号 | `8000` |

### 渐进式披露层级

MCP 服务器为 AI 代理实现了渐进式披露机制：

- **Layer 0**: `list_apps` - 发现可用的应用
- **Layer 1**: `list_queries`、`list_mutations` - 列出可用的操作
- **Layer 2**: `get_query_schema`、`get_mutation_schema` - 获取详细的 schema 信息
- **Layer 3**: `graphql_query`、`graphql_mutation` - 执行 GraphQL 操作

这让 AI 代理可以逐步探索和交互 GraphQL API，而不会被完整的 schema 信息淹没。

## 异常

- `ResolverTargetAttrNotFound`: 目标 field 不存在
- `LoaderFieldNotProvidedError`: Resolve 中没有提供 Loader 所需的参数
- `GlobalLoaderFieldOverlappedError`: `global_loader_params` 和 `loader_params` 参数出现重复
- `MissingCollector`: 找不到目标 collector, 祖先节点方法中未定义
- `MissingAnnotationError`: 使用 `AutoLoad` 或其他需要类型信息的注解时缺少类型注解
