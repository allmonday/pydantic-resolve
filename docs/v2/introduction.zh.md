# 简介

pydantic-resolve 是一个基于 pydantic 的轻量级封装库， 可以大幅简化构建数据的复杂度。

借助 pydantic 它可以像 GraphQL 一样用图的关系来描述数据结构, 也能够在获取数据的同时根据业务做调整。

在使用面向 ERD 的建模方式下,  它可以为你提供 3 ~ 5 倍的开发效率提升， 减少 50% 以上的代码量。

它为 pydantic 对象提供了 resolve 和 post 方法。

- resolve 通常用来获取数据
- post 可以在获取数据后做额外处理。

```python
class Car(BaseModel):
    id: int
    name: str
    produced_by: str
 
class Child(BaseModel):
    id: int
    name: str

    cars: List[Car] = []
    async def resolve_cars(self):
        return await get_cars_by_child(self.id)

    description: str = ''
    def post_description(self):
        desc = ', '.join([c.name for c in self.cars])
        return f'{self.name} owns {len(self.cars)} cars, they are: {desc}'

children = await Resolver.resolve([
        Child(id=1, name="Titan"),
        Child(id=1, name="Siri")]
    )
```

当定义完对象方法， 并初始化好对象后， pydantic-resolve 内部会对数据做遍历， 执行这些方法来处理数据， 最终获取所有数据

借助 dataloader， pydantic-resolve 可以避免多层获取数据时容易发生的 N+1 查询， 优化性能。

除此以外它还提供了 expose 和 collector 机制为跨层的数据处理提供了便利。

## 安装

```
pip install pydantic-resolve
```

从 pydantic-resolve v1.11.0 开始， 将同时兼容 pydantic v1 和 v2。
