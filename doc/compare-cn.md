# 和常见解决方案做一下比较 

## 和GraphQL相比

1. GraphQL的优势是 1.方便构建嵌套结构，2.client可以方便生成查询子集。非常适合构建满足灵活变化的 public API的场景.
2. 但是很多实际业务在前端做的其实是**照单全收**，并没有灵活选择的需要。GraphQL带来的便利更多体现在灵活地构建嵌套结构。
3. GraphQL需要client端维护查询语句，相较于通过`openapi.json`和工具自动生成client让前后端无缝对接的做法，在前后端一体的架构中维护这些查询语句，属于重复劳动。
4. 为了满足权限控制的需要，通过RESTful定义一个个API 会比全局一个Query，Mutation 控制起来更加清晰直接。
5. Pydantic-resolve 恰好满足了`灵活构建嵌套结构`的需求，它不需要像GraphQL一样引入一系列概念和设置，它非常轻量级，没有任何侵入，所有的功能通过简单`resolve`一下就实现。
6. Pydantic-resolve 在保持轻量级的同时，可以隐藏 Dataloader 的初始化逻辑，避免了GraphQL中在多处维护dataloader的麻烦。
7. Pydantic-resolve 还提供了对 global `loader filters` 的支持，在一些业务逻辑下可以简化很多代码。如果把Dataloader 的 keys 等价视为 relationship的 join on 条件的话， 那么 `loader_filters` 就类似在别处的其他过滤条件。

> 结论：
>
> 1. GraphQL更适合 public API。
>
> 2. 对**前后端作为一个整体**的项目，RESTful + Pydantic-resolve 才是快速灵活提供数据结构的最佳方法。


## 和 ORM 的 relationship相比

1. relationship 提供了ORM 级别的嵌套查询实现，但默认会使用lazy select的方法， 会导致很多的查询次数， 并且在异步使用的时候需要手动声明例如 `.option(subquery(Model.field))` 之类的代码
2. relationship 的外键决定了，无法在关联查询的时候提供额外的过滤条件 （即便可以也是改动成本比较大的做法）
3. relationship 最大的问题是使得 ORM Model 和 schema 产生了代码耦合。在schema层想做的嵌套查询，会把逻辑侵入到ORM Model层。
4. Pydantic-resolve 则没有这样的问题，在 ORM 层不需要定义任何relationship，所有的join逻辑都通过 dataloader 批量查询解决。 并且通过 global `loader_filters` 参数，可以提供额外的全局过滤条件。

> 结论
>
> 1. relationship 方案的灵活度低，不方便修改，默认的用法会产生外键约束。对迭代频繁的项目不友好。
>
> 2. Pydantic-resolve 和 ORM 层完全解耦，可以通过灵活创建Dataloader 来满足各种需要。