# 为什么写个新的库？

我是个 FastAPI（以及 starlette）的使用者，在写 pydantic-resolve 之前的一段时间，我写 API 用过两种方式：

- GraphQL，使用过一个小众的 python 库 pygraphy 和一个主流的库 strawberry-python。
- FastAPI 原生的 restful 风格接口，搭配 SQLAlchemy。

他们有各自的优点和缺点。

GraphQL 和 pydantic 两者的结合产生了写 pydantic-resolve 的灵感。

## GraphQL 的启发

使用 GraphQL 的初衷是为了提供灵活的后端数据接口，当定义清楚 Entity 和 Relationship 之后，用 GraphQL 就能提供许多通用的查询功能。（就像现在已经有许多工具能直接用 GraphQL 查询 db 了。）

在项目早期的时候，这为后端节省了许多的开发时间，当定义好数据之间的关联后，就能把所有的对象数据都提供给前端，让前端自行组合拼装。一开始合作非常的愉快。

但随着项目逐渐复杂，让前端维护一层数据转换的成本开始逐渐上升，比如前端可能会使用曲线救国的方式来查询数据，比如 project 对象没有定义 filter by has_team 的条件，于是前端可能会写出 team -> project 这样的查询。然后在前端再把数据转换成 project 的列表。随着功能迭代多了以后前端开始抱怨查询太慢。于是我逐渐意识到 GraphQL 声称的前后端不用沟通是个假象。

```graphql
query {
    team {
        project {
            id
            name
        }
    }
}
```

还有一种情况是后端的 schema 随着迭代定义变得混乱，比如 project 随着迭代会增加很多关联对象或者特殊计算值，但对查询者来说，这些信息并不是全部应该关注的，有时就搞不清楚该怎么写查询了。

```graphql
query {
    project {
        id
        name
        teams { ... }
        budgets { ... }
        members { ... }
    }
}
```

压垮 GraphQL 的最后稻草是权限控制，用 GraphQL 做过权限管控的自然懂，反正基于 node 的权限管控落地起来完全不现实，最后的妥协利用 query 的根节点，暴露不同的入口，最后就类似 restful 架构下的方案了，entry_1 和 entry_2 做了隔离，于是最早设想的灵活查询彻底变成了一个个静态的 schema。

```graphql
query {
    entry_1 {
        project {
            name
        }
    }

    entry_2 {
        team {
            name
            project {
                name
            }
        }
    }
}
```

这段过程给我了一些启发：

- GraphQL 的数据描述方式对前端非常友好，有层级嵌套的结构可以方便数据渲染。（但容易在后端形成不可复用的 schema）
- GraphQL 中图的模型，结合 ER 模型，可以复用大量 Entity 的查询。dataloader 能够优化 N+1 查询。
- 前端组合数据是一种错误实践，组合数据也是业务内容，业务侧统一管理才能长久维护。
- 前端查询 GraphQL query 也是一种错误实践，它会形成历史包袱，阻碍后端重构调整代码。最终两边都是脏代码。


## FastAPI 和 pydantic 的启发

接触到 FastAPI 和 pydantic 之后， 最让我印象深刻的是借助 pydantic 生成 openapi， 然后生成前端 typescript sdk 的功能。 （当然这不是 FastAPI 独有的）

它将前后端对接的成本直接减低了一个数量级， 所有的后端接口变更都能让前端感知到。 比如之前 GraphQL 虽然有了很多查询侧提供类型支持的工具， 但是终究还是需要写查询。

使用 FastAPI 之后前端就变成了

```python
const projects = await client.BusinessModuleA.getProjects()
```

这样简单粗暴的查询了。

随之而来的问题则是： 怎么构建像 GraphQL 那样的， 对前端友好的数据结构 ？？

使用 SQLAlchemy 的 relationship 能够获取到有关系结构的数据， 但是往往还需要对数据做重新遍历来调整数据和结构。

如果把调整写进查询的话， 又会导致大量的查询语句无法复用。

于是就陷入了一种矛盾的状态。

官方的推荐是书写一个和 model 定义很相似的 pydantic 类 （或者 dataclass 类）， 由这个 pydantic 对象来接收 orm 查询结果，类似 `Map<Model, DTO>` 的自动转换过程。

但 pydantic 类如果作为返回类型 （DTO）的话， 就很可能字段和 Model 有出入了。

我当时一直感觉这个过程有点鸡肋， 如果获取的数据和我期望的不同的话， 我就要额外遍历一次数据来做调整。 比如定义了 Item， Author 之后

```python
class Item(BaseModel):
    id: int
    name: str

class Author(BaseModel):
    id: int
    name: str
    items: List[Item]
```

Item 和 Author 在 Sqlalchemy 中定义了 relationship ， 可以一次性捞到关联数据。

如果我为了业务需求， 要额外根据一些复杂的业务逻辑过滤一下 Items， 或者 Item 中根据业务逻辑创建一个新字段， 就需要对 ORM 查询返回的 authors 和 items 做展开循环。

```python
for author in authors:
    business_process(author.items)

    for item in author.items:
        another_business_process(item)
        ...
```

层数少还行， 如果修改的内容多， 或者层数深， 都会导致类似的代码可读性和可维护性降低。

受到 graphene-python 的启发， 一个想法冒了出来， 为什么不就地定义一个 resolve_method 呢？

那我只要保证基础字段和 Model 中的一致，享受了 pydantic 自动 mapping 的便利， 然后用 resolve_method 原地做调整。

```python
class Item(BaseModel):
    id: int
    name: str
    new_field: str = ''
    def resolve_new_field(self):
        return business_process(self)

class Author(BaseModel):
    id: int
    name: str
    items: List[Item]
    def resolve_items(self):
        return business_process(self.items)
```

这样所有的操作行为都定义在了数据对象的内部， 而数据遍历过程交给代码自动遍历就好了， 遇到对应的类型执行内部的方法。

所以起初 resolve_method 只是对已有的数据做做处理。

然后发现 resolve_method 完全可以是异步的， 用来获取数据， 主要先给目标数据设置默认值， 然后在 resolve_method 中返回，设置数据。

但是直接 async 起手， 对于数组就会遇上 N+1 查询。

所以 DataLoader 就被引入进来解决这个问题。

于是 items 就变成了一个默认为 [] 的参数， 交由 ItemLoader 来获取数据， 这样一种按声明加载的模式

对于需要灵活组合的场景， 数据的加载可以用 类 的申明来驱动。

```python
class Item(BaseModel):
    id: int
    name: str
    new_field: str = ''
    def resolve_new_field(self):
        return business_process(self)

class Author(BaseModel):
    id: int
    name: str

    items: List[Item] = []
    async def resolve_items(self， loader=LoaderDepend(ItemLoader)):
        items =  await loader.load(self.id)
        return business_process(items)
```

意味着如果我没有为 Author 挂载 resolve_items 那么 ItemLoade 就不会被驱动执行。 一切都是class 的配置来驱动的。

```python
raw_authors = await get_authors()
authors = [Author.model_validate(a) for a in raw_authors]
authors = await Resolver().resolve(authors)
```

我只需要提供根节点的数据， pydantic-resolve 就会自动根据 Author 的配置来决定是否要关联子孙数据了。

换言之， 外部根数据和 resolve 相关的代码无需做调整， 关联配置的部分都集中维护在了 pydantic 类的内部。

有没有闻到一股子 GraphQL 写 query 的味道哈哈， 只是固化在了后端。

（btw 我觉得 DataLoader 这玩意比配置 ORM lazy 要方便一些）

然后既然固定的 pydantic 组合有独立的入口, 那么是不是可以为 DataLoader 添加额外参数?

再然后， 既然 resolve 代表了获取数据， 是否可以添加一个 post 钩子函数， 当所有 resolve 方法结束后， 对获取的数据做修改呢？

于是 post_methods 和 post_default_handler 就被添加了进来。

等等， 用 for 循环我可以读到祖先节点的变量， 这里怎么弄？？

所以 expose 和 collector 就被引入了进来。

迭代到了这里， 就差不多是 pydantic-resolve 的全部故事了。

我的开发模式就变成了：

- 先设计业务模型， 定义好 ER 模型
- 定义好 models， 定义好 pydantic 类， 定义好 DataLoaders （准备积木）
- 通过继承和扩展描述业务所需的数据结构， 使用 DataLoader 获取数据， 使用 post 方法调整数据 （搭积木， 做微调）
- 借助 FastAPI 和 TypeScript sdk generator 把方法和类型信息传送给前端
- 如果业务逻辑发生变化, 那么就调整或者添加申明的内容, 然后通过 sdk 把信息同步给前端

这种模式对业务早期调整频繁的情况有很强的适应能力， 针对数据关系的调整只需要重新申明组合， 或者新增 DataLoader 就足够了。（业务无关代码的噪音减小到最少）

而在项目业务稳定之后, 也能有充足的空间做性能优化, 比如将 DataLoader 的关联查询用一次性的查询结果来代替, 等等.

最后总结一下

3-5倍的开发效率是基于合理的，面向ER设计的 pydantic 类和 DataLoader, 被有效复用和组合的结果

50% 的代码量减少， 是继承和节省了遍历逻辑， 以及自动生成前端 sdk 的代码量。