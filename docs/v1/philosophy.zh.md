# 一个思考: 前后端对接应该怎么做?

## 简单到复杂

最初没有专职的前端， 页面的渲染都是后端的工作。

当浏览器功能复杂到一定程度，页面需求上升到一定程度，并且前端框架开始成熟， 独立的前端工种开始出现。

随之而来的变化， 是组织结构上，前后端的“分工”， 为了术业有专攻。

但伴随而来的问题是， “沟通”和“迭代” 成本的上升。

以前后端写页面的时候， 这也算是一种古老的全栈，一个人写节省了沟通成本。 并且通常会在controller 中提前把需要的数据组装好再render 到页面。

在分工的模式下， 一个功能，一个story 需要至少两个人来一起完成。 一人负责提供 API， 另一个人负责消费API 来构建页面。这些人都要参加需求会议， 还要保持一致的理解。产品遇到问题的时候， 往往就是先问前端， 然后排除前端嫌疑后再问后端， 路径就比较曲折， 前端也不胜其扰。

后端给API 会有两种选择， 可复用的功能， 做成通用API。尚不清楚全貌的功能， 做特供的API。通用的API 可能会在多个页面都有用到， 产生了多个依赖。

但业务总是在迭代， 早前通用的API 可能变得不通用， 导致的结果要么是后端对其做特殊的扩展， 要么是前端做多API 的组合。

（如果之前多个页面依赖了一个API， 则排查和调整的工作会更加复杂）

因此出现了技术债， API 参数变得复杂，前端则混入了组合数据的”业务逻辑“。

## 局部最优 不代表 全局最优

引出了一个观点， 在前后端合作的项目上，**不要去考虑”可复用的API”， 应该考虑可复用的“服务”**。 后端如果开始考虑API复用来减少自己的工作， 这可能往往就是麻烦的开始。

API 只是一个和页面相关联的“管道”， 每个页面有自己独立的“管道”， 和后端“供应商”。这样后续的维护和迭代才能容易。每个页面严格扮演好后端对应服务的展示层（presenter)。

如果发生了需求改变，影响的范围就只会出现在纵向，不会出现之前“改个API”， 结果某个其他页面报错的意外。

前后端分工后的另一个趋势是， 前端开始插手数据的处理，换个说法是开始做业务层相关的事情。

原因从可以从分工减少沟通的角度来解释，也可以从“充分利用”浏览器性能的角度来解释。 

但这样做带来的后果就是一个完整的业务逻辑被分散到了前后两端，这对业务的完整理解就会有害，而且越是迭代频繁的项目，这样做的麻烦就越多。

有一个概念叫做业务的本质复杂度，很多时候前后端分离模式下的代码的实现会在这层复杂度上增添厚厚的一层额外复杂度。

马丁福勒在《企业应用架构模式》中说：

> 处理领域逻辑时，其中一个最困难的部分就是区分什么是领域逻辑，什么是其他逻辑。我喜欢的一种不太正规的测试办法就是：假想向系统中增加一个完全不同的层，例如为Web应用增加一个命令行界面层。如果为了做到这一点，必须复制某些功能，则说明领域逻辑渗入了表示层。类似地，你也可以假想一下，将关系数据库更换成XML文件，看看情况又会如何？

上述的这种情况在前后端分离模式下是很容易出现的。

后端想着做通用接口， 前端想着做更多的事情， 两边的磨合的产物就是 BFF。

## BFF 模式的诞生 (其实也就是个controller)



BFF (backend for frontend) 出现的是引入了一个新的中间层，让后端专注在通用的的服务， 让前端专注在页面。 它来干中间的脏活， 构造特供的API。

他的责任是从多个数据源聚合数据，然后将处理完整的数据提供给对应的前端， 从而避免不必要的前端业务处理和数据转换操作。

如果后端service 的封装良好， 可以让前端在一层理想的业务抽象之上开发功能。

BFF 通常由前端来维护， 在BFF 模式下， BFF + 前端 组成了一个轻量级的全栈开发模式。它区分了领域层和展示层(presenter)。

这种分层在单体应用上对应的分层为 service, controller 和 presenter 三层。 约等于后端负责service， 前端负责controller 和 presenter。

- service 提供业务逻辑封装
- controller 组合各种业务逻辑， 满足各种灵活多变的数据需求
- presenter 展示数据
 
 
## 主流方案的比较

当前主流的BFF方案有graphql，trpc 和基于openapi 的 RESTful 。

1. graphql 存在引入成本较高，前端需要书写查询的问题， 还有其他graphql 的特有国情。（有空单开一页描述）

2. trpc 很好用，但限定了后端为 ts， 约束了后端选型。

综合来看，openapi 的 RESTful 接口，配合 openapi-ts 这类方案是最友好的，兼顾了后端实现的自由度和向前端提供类型和client 的便利。而且整个的引入成本也很小， 有不少的框架都支持自动生成 openapi 接口文档。 

另外这个方案对功能迭代非常友好， **后端如果修改了方法和返回结构， 只要重新生成 client，前端 （如果是ts） 就能立刻感知类型和接口发生的变化。**

在确定了openapi 的方向之后，问题就简化成了，怎样才能方便地从多个数据源/数据库组合出来需要的数据？


## 继承，扩展 schema，以申明的方式来构造数据

利用orm 是一种手段， 但这个局限于数据库关联数据查询， 如果是跨多个服务的数据拼接， 常见的手段依然是手动循环拼接。

这个方面graphql做得很好，搭配resolve 和 dataloader 可以轻松得组合出自己所需的数据结构。在 resolver 中， 数据源既可以是orm 的返回值， 也可以是第三方接口调用的数据。

schema 申明了数据结构（接口定义）， resolver 为所申明的数据结构提供真实数据（具体实现）。

dataloader 则提供了通用的解决 N+1 查询的方法。

按照上述的逻辑， 以FastAPI pydantic 为例, 

1. 我们可以通过简单的继承来扩展已有的schema， 添加所需的关联数据
2. 让resolver 来负责数据的具体加载

```python
class Sample1TeamDetail(tms.Team):
    sprints: list[Sample1SprintDetail] = []
    def resolve_sprints(self, loader=LoaderDepend(spl.team_to_sprint_loader)):
        return loader.load(self.id)
    
    members: list[us.User] = []
    def resolve_members(self, loader=LoaderDepend(ul.team_to_user_loader)):
        return loader.load(self.id)

class Sample1SprintDetail(sps.Sprint):
    stories: list[Sample1StoryDetail] = []
    def resolve_stories(self, loader=LoaderDepend(sl.sprint_to_story_loader)):
        return loader.load(self.id)

class Sample1StoryDetail(ss.Story):
    tasks: list[Sample1TaskDetail] = []
    def resolve_tasks(self, loader=LoaderDepend(tl.story_to_task_loader)):
        return loader.load(self.id)

    owner: Optional[us.User] = None
    def resolve_owner(self, loader=LoaderDepend(ul.user_batch_loader)):
        return loader.load(self.owner_id)

class Sample1TaskDetail(ts.Task):
    user: Optional[us.User] = None
    def resolve_user(self, loader=LoaderDepend(ul.user_batch_loader)):
        return loader.load(self.owner_id)
```

在定义完了期望的多层schema 之后，我们只需要提供 root 数据， 既 Team 的数据， 其他 sprint, story, task 的数据都会在 resolve 的过程中自动获取到。
借助dataloader 这样的过程只会触发额外三次查询。

```python
@route.get('/teams-with-detail', response_model=List[Sample1TeamDetail])
async def get_teams_with_detail(session: AsyncSession = Depends(db.get_session)):
    teams = await tmq.get_teams(session)
    teams = [Sample1TeamDetail.model_validate(t) for t in teams]
    teams = await Resolver().resolve(teams)
    return teams
```

在这样的模式下：

1. service 层只需要提供 root 数据的查询， 和关联数据的 dataloader （batch query)， 就能高枕无忧
2. controller 层则只要对schema 做简单的扩展， 并且调用合适的 dataloader， 就能轻松得组合出期望的数据


## 总结

1.  为每个页面提供独立的API， 可以减少迭代中产生的问题。 也为接口优化提供了空间。 不复用API， 复用 service。
2. 通过继承扩展 schema ， 结合 resolver 模式， 可以在数据组合的效率上和 graphql 相媲美， 为每个页面构造独立的 API
3. RESTFul 配合 openapi-ts 之类的 client 生成工具， 可以将方法和类型信息无缝传递给前端。

> 每个页面独立的 API, 概念类似每个页面有个独立的 render(page_name, data)

这个模式在全栈的开发模式下的效率非常高， 自己定义好的接口， 一行命令 generate 就能在前端直接使用，特别清爽。 对比graphql 省去了前端敲 query 的麻烦。







