# 先定义模型，再描述获取方式

使用 pydantic-resolve 的推荐方式是先定义模型。 将所有的操作都附加在定义好的数据对象上。

当我们构建数据时， 一个很朴素的思考方式是：先定义好目标数据结构 Target， 比较当前已有的数据源结构 Source ，寻找最短的变化路径。

> 更加详细的内容会在 "ERD 驱动开发" 中介绍。

比如我有一个 Person 的数组， 现在要为每个人增加请假信息， 数据库中已有的请假数据包含年假，病假两种， 要把两者合并成一个类型。

## 期望的结构

期望的数据结构就是 Person 和对应的 absenses, Absense 是面向业务的数据结构。

```python
class Person(BaseModel):
    id: int
    name: str
    absenses: List[Absense]

class Absense(BaseModel):
    type: Literal['annual', 'sick']
    start_date: date
    end_date: date
```

## 添加数据源

AnnualLeave 和 SickLeave 是已有的数据类型。

分别由 AnnualLeaveLoader 和 SickLeaveLoader 提供具体数据。

```python
class AnnualLeave(BaseModel):
    person_id: int
    start_date: date
    end_date: date

class SickLeave(BaseModel):
    person_id: int
    start_date: date
    end_date: date
```

此时我们可以把源数据和期望数据组合在一起, 列出好需要获取的数据和将要计算出来的结果。

这代表了起始数据和目标数据。

配合 `exclude=True` 可以在最终输出中隐藏临时变量。

```python
@model_config()
class Person(BaseModel):
    id: int
    name: str

    annual_leaves: List[AnnualLeave] = Field(default_factory=list, exclude=True)
    sick_leaves: List[SickLeave] = Field(default_factory=list, exclude=True)

    absenses: List[Absense] = []
```

## 加载数据

然后我们为 `annual_leaves` 和 `sick_leaves` 添加 resolve 和 dataloader， 他们将为起始数据提供数据。

```python
@model_config()
class Person(BaseModel):
    id: int
    name: str

    annual_leaves: List[AnnualLeave] = Field(default_factory=list, exclude=True)
    def resolve_annual_leaves(self, loader=LoaderDepend(AnnualLeaveLoader)):
        return loader.load(self.id)

    sick_leaves: List[SickLeave] = Field(default_factory=list, exclude=True)
    def resolve_sick_leaves(self, loader=LoaderDepend(SickLeaveLoader)):
        return loader.load(self.id)

    absense: List[Absense] = []
```

## 转换数据

当 `annual_leaves` 和 `sick_leaves` 的 resolve 阶段结束时， 他们已经有实际数据了， 接下来利用 post 阶段来计算 absenses

```python
@model_config()
class Person(BaseModel):
    id: int
    name: str

    annual_leaves: List[AnnualLeave] = Field(default_factory=list, exclude=True)
    def resolve_annual_leaves(self, loader=LoaderDepend(AnnualLeaveLoader)):
        return loader.load(self.id)

    sick_leaves: List[SickLeave] = Field(default_factory=list, exclude=True)
    def resolve_sick_leaves(self, loader=LoaderDepend(SickLeaveLoader)):
        return loader.load(self.id)

    absenses: List[Absense] = []
    def post_absense(self):
        a = [Absense(
                type='annual',
                start_date=a.start_date,
                end_date=a.end_date) for a in self.annual_leaves]
        b = [Absense(
                type='sick',
                start_date=s.start_date,
                end_date=s.end_date) for a in self.sick_leaves]
        return a + b
```

## 启动整个过程

当定义完整个 Person, Absense 的结构后， 我们就能通过初始化 people 来加载和计算所有数据了，只需对 people 数据执行一次 Resolver().resolve() 就能完成所有的操作。

```python
people = [Person(id=1, name='alice'), Person(id=2, name='bob')]
people = await Resolver().resolve(people)
```

在这整个拼装过程中， 我们没有书写一行循环展开 people 的代码，所有的相关代码都在 Person 对象的内部。

如果使用面向过程的方式来处理的话， 会需要至少考虑：

- annual, sick leaves 根据 person_id 聚合，生成 person_annual_map 和 person_sick_map 两个新变量
- `for person in people` 遍历 person 对象

这些过程在 pydantic-resolve 都是内部封装掉了的。
